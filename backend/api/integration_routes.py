"""
Integration API Routes
REST endpoints for managing external integrations (Gmail, Slack, Box, etc.)
"""

import os
import secrets
import jwt
import time
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote
from datetime import datetime, timezone, timedelta
from flask import Blueprint, request, jsonify, g, redirect

from database.models import (
    SessionLocal, Connector, Document, Tenant, DeletedDocument,
    ConnectorType, ConnectorStatus, DocumentStatus, DocumentClassification,
    generate_uuid, utc_now
)
from database.config import JWT_SECRET_KEY, JWT_ALGORITHM
from services.auth_service import require_auth, get_token_from_header, JWTUtils
from services.embedding_service import get_embedding_service
from services.extraction_service import get_extraction_service


# Create blueprint
integration_bp = Blueprint('integrations', __name__, url_prefix='/api/integrations')


def _get_oauth_redirect_uri(connector_type: str) -> str:
    """
    Get the OAuth redirect URI for a connector, auto-detecting the backend URL
    from the request if the env var isn't set. Works behind Render's proxy.
    """
    # Check for explicit env var first (e.g. NOTION_REDIRECT_URI, GOOGLE_REDIRECT_URI)
    env_key = {
        'notion': 'NOTION_REDIRECT_URI',
        'gmail': 'GOOGLE_REDIRECT_URI',
        'gdrive': 'GDRIVE_REDIRECT_URI',
        'gdocs': 'GDOCS_REDIRECT_URI',
        'gsheets': 'GSHEETS_REDIRECT_URI',
        'gslides': 'GSLIDES_REDIRECT_URI',
        'gcalendar': 'GCALENDAR_REDIRECT_URI',
        'slack': 'SLACK_REDIRECT_URI',
        'box': 'BOX_REDIRECT_URI',
        'github': 'GITHUB_REDIRECT_URI',
        'onedrive': 'MICROSOFT_REDIRECT_URI',
        'outlook': 'OUTLOOK_REDIRECT_URI',
    }.get(connector_type)

    if env_key:
        explicit = os.getenv(env_key)
        if explicit:
            return explicit

    # Auto-detect from request (respects X-Forwarded-Proto behind Render proxy)
    scheme = request.headers.get('X-Forwarded-Proto', request.scheme)
    host = request.headers.get('X-Forwarded-Host', request.host)
    base = f"{scheme}://{host}"

    # Map connector type to callback path
    callback_type = connector_type
    if connector_type == 'gdrive':
        callback_type = 'gdrive'
    elif connector_type == 'onedrive':
        callback_type = 'onedrive'

    uri = f"{base}/api/integrations/{callback_type}/callback"
    print(f"[OAuth] Auto-detected redirect_uri for {connector_type}: {uri}", flush=True)
    return uri


def safe_error_redirect(base_url: str, error: str) -> str:
    """
    Create a safe redirect URL with an error parameter.
    Sanitizes the error message to remove newlines and URL-encodes it.
    """
    # Take first line and limit length to avoid overly long URLs
    safe_error = str(error).split('\n')[0][:200]
    return redirect(f"{base_url}?error={quote(safe_error)}")


# ============================================================================
# SLACK EVENT DEDUPLICATION (prevents Slack retries causing duplicate responses)
# ============================================================================
# Slack retries events if it doesn't get a 200 response within 3 seconds.
# We cache event_ids for 60 seconds to prevent processing the same event twice.

_processed_events = {}  # event_id -> timestamp
_events_lock = threading.Lock()
DEDUP_TTL_SECONDS = 60  # Keep event IDs for 60 seconds


def _is_duplicate_event(event_id: str) -> bool:
    """Check if event was already processed (and clean old entries)"""
    if not event_id:
        return False

    now = time.time()

    with _events_lock:
        # Clean old entries
        expired = [k for k, v in _processed_events.items() if now - v > DEDUP_TTL_SECONDS]
        for k in expired:
            del _processed_events[k]

        # Check if already processed
        if event_id in _processed_events:
            print(f"[Slack Events] DUPLICATE event {event_id} - skipping", flush=True)
            return True

        # Mark as processed
        _processed_events[event_id] = now
        return False


# ============================================================================
# SECURE OAUTH STATE MANAGEMENT (JWT-based, stateless)
# ============================================================================

def create_oauth_state(tenant_id: str, user_id: str, connector_type: str, extra_data: dict = None) -> str:
    """
    Create a secure, signed OAuth state token.
    This eliminates the need for server-side state storage (Redis/memory).

    The state is a JWT containing:
    - tenant_id: The tenant making the request
    - user_id: The user initiating the OAuth
    - connector_type: Which connector (gmail, slack, box)
    - exp: Expiration (10 minutes)
    - nonce: Random value for uniqueness
    """
    payload = {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "connector_type": connector_type,
        "nonce": secrets.token_urlsafe(16),
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
        "type": "oauth_state"
    }
    if extra_data:
        payload["data"] = extra_data

    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def verify_oauth_state(state: str) -> tuple:
    """
    Verify and decode an OAuth state token.

    Returns:
        (payload, error) - payload dict if valid, None and error message if invalid
    """
    try:
        payload = jwt.decode(state, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])

        if payload.get("type") != "oauth_state":
            return None, "Invalid state type"

        return payload, None
    except jwt.ExpiredSignatureError:
        return None, "OAuth state expired. Please try again."
    except jwt.InvalidTokenError as e:
        return None, f"Invalid OAuth state: {str(e)}"


# Legacy oauth_states dict - kept for backward compatibility during transition
# TODO: Remove after all OAuth flows are migrated to JWT-based state
oauth_states = {}

# Sync progress tracking (use Redis in production for multi-instance)
sync_progress = {}
_sync_progress_lock = threading.RLock()  # Protects sync_progress dict from concurrent access

# Thread pool for sync operations (prevents unbounded thread creation)
_sync_executor = ThreadPoolExecutor(max_workers=20, thread_name_prefix='sync')


def get_db():
    """Get database session"""
    return SessionLocal()


def _update_sync_progress(key: str, updates: dict = None, init: dict = None):
    """Thread-safe update to sync_progress dict."""
    with _sync_progress_lock:
        if init is not None:
            sync_progress[key] = init
        elif key in sync_progress and updates:
            sync_progress[key].update(updates)


def _get_sync_progress(key: str) -> dict:
    """Thread-safe read from sync_progress dict."""
    with _sync_progress_lock:
        return dict(sync_progress.get(key, {}))


# ============================================================================
# LIST INTEGRATIONS
# ============================================================================

@integration_bp.route('', methods=['GET'])
@require_auth
def list_integrations():
    """
    List all integrations for the current tenant.

    Response:
    {
        "success": true,
        "integrations": [
            {
                "type": "gmail",
                "name": "Gmail",
                "status": "connected",
                "last_sync_at": "2024-01-15T10:30:00Z",
                ...
            }
        ]
    }
    """
    try:
        db = get_db()
        try:
            # Get existing connectors for tenant
            connectors = db.query(Connector).filter(
                Connector.tenant_id == g.tenant_id,
                Connector.is_active == True
            ).all()

            # Build response with all connector types
            connector_map = {c.connector_type: c for c in connectors}

            integrations = []

            # Gmail
            gmail = connector_map.get(ConnectorType.GMAIL)
            integrations.append({
                "type": "gmail",
                "name": "Gmail",
                "description": "Sync emails from your Gmail account",
                "icon": "mail",
                "auth_type": "oauth",
                "status": gmail.status.value if gmail else "not_configured",
                "connector_id": gmail.id if gmail else None,
                "last_sync_at": gmail.last_sync_at.isoformat() if gmail and gmail.last_sync_at else None,
                "total_items_synced": gmail.total_items_synced if gmail else 0,
                "error_message": gmail.error_message if gmail else None
            })

            # Slack
            slack = connector_map.get(ConnectorType.SLACK)
            integrations.append({
                "type": "slack",
                "name": "Slack",
                "description": "Sync messages from Slack workspaces",
                "icon": "slack",
                "auth_type": "oauth",
                "status": slack.status.value if slack else "not_configured",
                "connector_id": slack.id if slack else None,
                "last_sync_at": slack.last_sync_at.isoformat() if slack and slack.last_sync_at else None,
                "total_items_synced": slack.total_items_synced if slack else 0,
                "error_message": slack.error_message if slack else None
            })

            # Box
            box = connector_map.get(ConnectorType.BOX)
            integrations.append({
                "type": "box",
                "name": "Box",
                "description": "Sync files and documents from Box",
                "icon": "box",
                "auth_type": "oauth",
                "status": box.status.value if box else "not_configured",
                "connector_id": box.id if box else None,
                "last_sync_at": box.last_sync_at.isoformat() if box and box.last_sync_at else None,
                "total_items_synced": box.total_items_synced if box else 0,
                "error_message": box.error_message if box else None
            })

            # GitHub (optional)
            github = connector_map.get(ConnectorType.GITHUB)
            integrations.append({
                "type": "github",
                "name": "GitHub",
                "description": "Sync code, issues, and PRs from GitHub",
                "icon": "github",
                "auth_type": "oauth",
                "status": github.status.value if github else "not_configured",
                "connector_id": github.id if github else None,
                "last_sync_at": github.last_sync_at.isoformat() if github and github.last_sync_at else None,
                "total_items_synced": github.total_items_synced if github else 0,
                "error_message": github.error_message if github else None
            })

            # OneDrive (Microsoft 365)
            onedrive = connector_map.get(ConnectorType.ONEDRIVE)
            integrations.append({
                "type": "onedrive",
                "name": "Microsoft 365",
                "description": "Sync documents from OneDrive and SharePoint",
                "icon": "onedrive",
                "auth_type": "oauth",
                "status": onedrive.status.value if onedrive else "not_configured",
                "connector_id": onedrive.id if onedrive else None,
                "last_sync_at": onedrive.last_sync_at.isoformat() if onedrive and onedrive.last_sync_at else None,
                "total_items_synced": onedrive.total_items_synced if onedrive else 0,
                "error_message": onedrive.error_message if onedrive else None
            })

            # PubMed (research)
            pubmed = connector_map.get(ConnectorType.PUBMED)
            integrations.append({
                "type": "pubmed",
                "name": "PubMed",
                "description": "Search biomedical literature from NCBI",
                "icon": "pubmed",
                "auth_type": "api_key",
                "status": pubmed.status.value if pubmed else "not_configured",
                "connector_id": pubmed.id if pubmed else None,
                "last_sync_at": pubmed.last_sync_at.isoformat() if pubmed and pubmed.last_sync_at else None,
                "total_items_synced": pubmed.total_items_synced if pubmed else 0,
                "error_message": pubmed.error_message if pubmed else None,
                "settings": pubmed.settings if pubmed else None
            })

            # Quartzy (lab inventory)
            quartzy = connector_map.get(ConnectorType.QUARTZY)
            integrations.append({
                "type": "quartzy",
                "name": "Quartzy",
                "description": "Import lab inventory items and order requests",
                "icon": "quartzy",
                "auth_type": "api_key",
                "status": quartzy.status.value if quartzy else "not_configured",
                "connector_id": quartzy.id if quartzy else None,
                "last_sync_at": quartzy.last_sync_at.isoformat() if quartzy and quartzy.last_sync_at else None,
                "total_items_synced": quartzy.total_items_synced if quartzy else 0,
                "error_message": quartzy.error_message if quartzy else None,
                "settings": quartzy.settings if quartzy else None
            })

            # Website Scraper (legacy BFS crawler)
            webscraper = connector_map.get(ConnectorType.WEBSCRAPER)
            integrations.append({
                "type": "webscraper",
                "name": "Website Scraper (Legacy)",
                "description": "Crawl websites to extract protocols and documentation",
                "icon": "webscraper",
                "auth_type": "config",
                "status": webscraper.status.value if webscraper else "not_configured",
                "connector_id": webscraper.id if webscraper else None,
                "last_sync_at": webscraper.last_sync_at.isoformat() if webscraper and webscraper.last_sync_at else None,
                "total_items_synced": webscraper.total_items_synced if webscraper else 0,
                "error_message": webscraper.error_message if webscraper else None,
                "settings": webscraper.settings if webscraper else None
            })

            # Firecrawl (full website crawler with JS rendering, PDF support)
            firecrawl = connector_map.get(ConnectorType.FIRECRAWL)
            integrations.append({
                "type": "firecrawl",
                "name": "Website Firecrawler",
                "description": "Crawl entire websites with JS rendering, PDF extraction, and sitemap discovery. Powered by Firecrawl.",
                "icon": "webscraper",
                "auth_type": "config",
                "status": firecrawl.status.value if firecrawl else "not_configured",
                "connector_id": firecrawl.id if firecrawl else None,
                "last_sync_at": firecrawl.last_sync_at.isoformat() if firecrawl and firecrawl.last_sync_at else None,
                "total_items_synced": firecrawl.total_items_synced if firecrawl else 0,
                "error_message": firecrawl.error_message if firecrawl else None,
                "settings": firecrawl.settings if firecrawl else None
            })

            # Notion
            notion = connector_map.get(ConnectorType.NOTION)
            integrations.append({
                "type": "notion",
                "name": "Notion",
                "description": "Sync pages and databases from Notion",
                "icon": "notion",
                "auth_type": "oauth",
                "status": notion.status.value if notion else "not_configured",
                "connector_id": notion.id if notion else None,
                "last_sync_at": notion.last_sync_at.isoformat() if notion and notion.last_sync_at else None,
                "total_items_synced": notion.total_items_synced if notion else 0,
                "error_message": notion.error_message if notion else None
            })

            # Google Drive
            gdrive = connector_map.get(ConnectorType.GOOGLE_DRIVE)
            integrations.append({
                "type": "gdrive",
                "name": "Google Drive",
                "description": "Sync files (PDF, DOCX, etc.) from Google Drive",
                "icon": "gdrive",
                "auth_type": "oauth",
                "status": gdrive.status.value if gdrive else "not_configured",
                "connector_id": gdrive.id if gdrive else None,
                "last_sync_at": gdrive.last_sync_at.isoformat() if gdrive and gdrive.last_sync_at else None,
                "total_items_synced": gdrive.total_items_synced if gdrive else 0,
                "error_message": gdrive.error_message if gdrive else None
            })

            # Google Docs
            gdocs = connector_map.get(ConnectorType.GOOGLE_DOCS)
            integrations.append({
                "type": "gdocs",
                "name": "Google Docs",
                "description": "Sync Google Docs documents",
                "icon": "gdocs",
                "auth_type": "oauth",
                "status": gdocs.status.value if gdocs else "not_configured",
                "connector_id": gdocs.id if gdocs else None,
                "last_sync_at": gdocs.last_sync_at.isoformat() if gdocs and gdocs.last_sync_at else None,
                "total_items_synced": gdocs.total_items_synced if gdocs else 0,
                "error_message": gdocs.error_message if gdocs else None
            })

            # Google Sheets
            gsheets = connector_map.get(ConnectorType.GOOGLE_SHEETS)
            integrations.append({
                "type": "gsheets",
                "name": "Google Sheets",
                "description": "Sync Google Sheets spreadsheets",
                "icon": "gsheets",
                "auth_type": "oauth",
                "status": gsheets.status.value if gsheets else "not_configured",
                "connector_id": gsheets.id if gsheets else None,
                "last_sync_at": gsheets.last_sync_at.isoformat() if gsheets and gsheets.last_sync_at else None,
                "total_items_synced": gsheets.total_items_synced if gsheets else 0,
                "error_message": gsheets.error_message if gsheets else None
            })

            # Google Slides
            gslides = connector_map.get(ConnectorType.GOOGLE_SLIDES)
            integrations.append({
                "type": "gslides",
                "name": "Google Slides",
                "description": "Sync Google Slides presentations",
                "icon": "gslides",
                "auth_type": "oauth",
                "status": gslides.status.value if gslides else "not_configured",
                "connector_id": gslides.id if gslides else None,
                "last_sync_at": gslides.last_sync_at.isoformat() if gslides and gslides.last_sync_at else None,
                "total_items_synced": gslides.total_items_synced if gslides else 0,
                "error_message": gslides.error_message if gslides else None
            })

            # Google Calendar
            gcalendar = connector_map.get(ConnectorType.GOOGLE_CALENDAR)
            integrations.append({
                "type": "gcalendar",
                "name": "Google Calendar",
                "description": "Sync events from Google Calendar",
                "icon": "gcalendar",
                "auth_type": "oauth",
                "status": gcalendar.status.value if gcalendar else "not_configured",
                "connector_id": gcalendar.id if gcalendar else None,
                "last_sync_at": gcalendar.last_sync_at.isoformat() if gcalendar and gcalendar.last_sync_at else None,
                "total_items_synced": gcalendar.total_items_synced if gcalendar else 0,
                "error_message": gcalendar.error_message if gcalendar else None
            })

            # Zotero
            zotero = connector_map.get(ConnectorType.ZOTERO)
            integrations.append({
                "type": "zotero",
                "name": "Zotero",
                "description": "Sync research papers and citations from Zotero",
                "icon": "zotero",
                "auth_type": "oauth",
                "status": zotero.status.value if zotero else "not_configured",
                "connector_id": zotero.id if zotero else None,
                "last_sync_at": zotero.last_sync_at.isoformat() if zotero and zotero.last_sync_at else None,
                "total_items_synced": zotero.total_items_synced if zotero else 0,
                "error_message": zotero.error_message if zotero else None,
                "settings": {
                    "library_id": zotero.settings.get("library_id") if zotero and zotero.settings else None,
                    "library_type": zotero.settings.get("library_type") if zotero and zotero.settings else None
                } if zotero else None
            })

            return jsonify({
                "success": True,
                "integrations": integrations,
                "connected_count": sum(1 for i in integrations if i["status"] == "connected")
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# GMAIL INTEGRATION
# ============================================================================

@integration_bp.route('/gmail/auth', methods=['GET'])
@require_auth
def gmail_auth():
    """
    Start Gmail OAuth flow.

    Response:
    {
        "success": true,
        "auth_url": "https://accounts.google.com/...",
        "state": "..."
    }
    """
    try:
        from connectors.gmail_connector import GmailConnector

        # Generate JWT-based state (works across multiple workers)
        redirect_uri = os.getenv(
            "GOOGLE_REDIRECT_URI",
            "http://localhost:5003/api/integrations/gmail/callback"
        )

        state = create_oauth_state(
            tenant_id=g.tenant_id,
            user_id=g.user_id,
            connector_type="gmail",
            extra_data={"redirect_uri": redirect_uri}
        )
        print(f"[GmailAuth] JWT state created for tenant: {g.tenant_id}")

        # Get auth URL
        auth_url = GmailConnector.get_auth_url(redirect_uri, state)

        return jsonify({
            "success": True,
            "auth_url": auth_url,
            "state": state
        })

    except ImportError:
        return jsonify({
            "success": False,
            "error": "Gmail dependencies not installed. Run: pip install google-auth google-auth-oauthlib google-api-python-client"
        }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@integration_bp.route('/gmail/callback', methods=['GET'])
def gmail_callback():
    """
    Gmail OAuth callback handler.
    Called by Google after user authorization.
    """
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

    try:
        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')

        if error:
            return redirect(f"{FRONTEND_URL}/integrations?error={error}")

        if not code or not state:
            return redirect(f"{FRONTEND_URL}/integrations?error=missing_params")

        # Verify JWT-based state
        state_data, error_msg = verify_oauth_state(state)
        if error_msg or not state_data or state_data.get("connector_type") != "gmail":
            print(f"[Gmail Callback] Invalid state: {error_msg}")
            return redirect(f"{FRONTEND_URL}/integrations?error=invalid_state")

        from connectors.gmail_connector import GmailConnector

        # Exchange code for tokens
        redirect_uri = state_data.get("data", {}).get("redirect_uri")
        if not redirect_uri:
            redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:5003/api/integrations/gmail/callback")
        tokens, error = GmailConnector.exchange_code_for_tokens(code, redirect_uri)

        if error:
            return redirect(f"{FRONTEND_URL}/integrations?error={error}")

        # Save connector to database
        db = get_db()
        try:
            tenant_id = state_data.get("tenant_id")
            user_id = state_data.get("user_id")

            # Check if connector already exists
            connector = db.query(Connector).filter(
                Connector.tenant_id == tenant_id,
                Connector.connector_type == ConnectorType.GMAIL
            ).first()

            is_first_connection = connector is None

            if connector:
                # Update existing
                connector.access_token = tokens["access_token"]
                connector.refresh_token = tokens["refresh_token"]
                connector.status = ConnectorStatus.CONNECTED
                connector.is_active = True  # Re-enable connector on reconnect
                connector.error_message = None
                connector.updated_at = utc_now()
                print(f"[Gmail Callback] Updated existing connector for tenant: {tenant_id}")
            else:
                # Create new
                connector = Connector(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    connector_type=ConnectorType.GMAIL,
                    name="Gmail",
                    status=ConnectorStatus.CONNECTED,
                    access_token=tokens["access_token"],
                    refresh_token=tokens["refresh_token"],
                    token_scopes=["https://www.googleapis.com/auth/gmail.readonly"]
                )
                db.add(connector)
                print(f"[Gmail Callback] Created new connector for tenant: {tenant_id}")

            db.commit()

            # Auto-sync on first connection
            if is_first_connection:
                connector_id = connector.id
                tenant_id = state_data["tenant_id"]
                user_id = state_data["user_id"]

                def run_initial_sync():
                    _run_connector_sync(
                        connector_id=connector_id,
                        connector_type="gmail",
                        since=None,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        full_sync=True
                    )

                thread = threading.Thread(target=run_initial_sync)
                thread.daemon = True
                thread.start()

                print(f"[Gmail Callback] Started auto-sync for first-time connection")

            return redirect(f"{FRONTEND_URL}/integrations?success=gmail")

        finally:
            db.close()

    except Exception as e:
        return redirect(f"{FRONTEND_URL}/integrations?error={quote(str(e))}")


# ============================================================================
# SLACK INTEGRATION
# ============================================================================

@integration_bp.route('/slack/auth', methods=['GET'])
@require_auth
def slack_auth():
    """
    Start Slack OAuth flow.
    """
    try:
        # Generate JWT-based state (works across multiple workers)
        state = create_oauth_state(
            tenant_id=g.tenant_id,
            user_id=g.user_id,
            connector_type="slack"
        )

        # Build Slack OAuth URL
        client_id = os.getenv("SLACK_CLIENT_ID", "")
        redirect_uri = os.getenv(
            "SLACK_REDIRECT_URI",
            "http://localhost:5003/api/integrations/slack/callback"
        )

        # Check if credentials are configured
        if not client_id:
            return jsonify({
                "success": False,
                "error": "Slack integration not configured. Please set SLACK_CLIENT_ID and SLACK_CLIENT_SECRET in your environment."
            }), 400

        # Comprehensive scopes for reading all messages
        # channels:read - View basic channel info
        # channels:history - View messages in public channels
        # channels:join - Join public channels (to access all channels)
        # groups:read - View private channels info
        # SYNCING SCOPES:
        # channels:read,channels:history,channels:join - Read public channels
        # groups:read,groups:history - Read private channels the bot is in
        # im:history,mpim:history - Read direct messages
        # users:read - View user info (for resolving @mentions)
        # team:read - View workspace info
        #
        # CHATBOT SCOPES (for responding to questions):
        # chat:write - Send messages (CRITICAL for chatbot!)
        # app_mentions:read - Hear @mentions
        # commands - Receive slash commands like /ask
        # im:write - Send DMs
        scopes = "channels:read,channels:history,channels:join,groups:read,groups:history,im:history,im:write,mpim:history,users:read,team:read,chat:write,app_mentions:read,commands"

        auth_url = (
            f"https://slack.com/oauth/v2/authorize"
            f"?client_id={client_id}"
            f"&scope={scopes}"
            f"&redirect_uri={redirect_uri}"
            f"&state={state}"
        )

        return jsonify({
            "success": True,
            "auth_url": auth_url,
            "state": state
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@integration_bp.route('/slack/channels', methods=['GET'])
@require_auth
def slack_channels():
    """
    Get list of Slack channels for selection.
    User can choose which channels to sync.
    """
    try:
        import requests

        db = get_db()
        try:
            connector = db.query(Connector).filter(
                Connector.tenant_id == g.tenant_id,
                Connector.connector_type == ConnectorType.SLACK,
                Connector.status == ConnectorStatus.CONNECTED
            ).first()

            if not connector:
                return jsonify({
                    "success": False,
                    "error": "Slack not connected"
                }), 400

            # Get channels from Slack API
            response = requests.get(
                "https://slack.com/api/conversations.list",
                headers={"Authorization": f"Bearer {connector.access_token}"},
                params={
                    "types": "public_channel,private_channel",
                    "exclude_archived": "true",
                    "limit": 200
                }
            )

            data = response.json()

            if not data.get("ok"):
                return jsonify({
                    "success": False,
                    "error": data.get("error", "Failed to fetch channels")
                }), 400

            # Get currently selected channels from settings
            current_settings = connector.settings or {}
            selected_channels = current_settings.get("channels", [])

            channels = []
            for ch in data.get("channels", []):
                channels.append({
                    "id": ch["id"],
                    "name": ch["name"],
                    "is_private": ch.get("is_private", False),
                    "is_member": ch.get("is_member", False),
                    "member_count": ch.get("num_members", 0),
                    "selected": ch["id"] in selected_channels or len(selected_channels) == 0
                })

            return jsonify({
                "success": True,
                "channels": channels,
                "total": len(channels),
                "selected_count": len(selected_channels) if selected_channels else len(channels)
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@integration_bp.route('/slack/channels', methods=['PUT'])
@require_auth
def update_slack_channels():
    """
    Update which Slack channels to sync.
    """
    try:
        data = request.get_json()
        channel_ids = data.get("channels", [])

        db = get_db()
        try:
            connector = db.query(Connector).filter(
                Connector.tenant_id == g.tenant_id,
                Connector.connector_type == ConnectorType.SLACK,
                Connector.is_active == True
            ).first()

            if not connector:
                return jsonify({
                    "success": False,
                    "error": "Slack not connected"
                }), 400

            # Update settings
            current_settings = connector.settings or {}
            current_settings["channels"] = channel_ids
            connector.settings = current_settings
            connector.updated_at = utc_now()

            db.commit()

            return jsonify({
                "success": True,
                "message": f"Updated to sync {len(channel_ids)} channels",
                "channels": channel_ids
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@integration_bp.route('/slack/token', methods=['POST'])
@require_auth
def slack_token():
    """
    Connect Slack using a Bot User OAuth Token directly.
    This is simpler than OAuth flow for internal/development apps.

    Request body:
    {
        "access_token": "xoxb-..."
    }
    """
    try:
        import requests as req

        data = request.get_json()
        access_token = data.get("access_token", "")

        if not access_token.startswith("xoxb-"):
            return jsonify({
                "success": False,
                "error": "Invalid token format. Token should start with 'xoxb-'"
            }), 400

        # Test the token by calling auth.test
        test_response = req.get(
            "https://slack.com/api/auth.test",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        test_data = test_response.json()

        if not test_data.get("ok"):
            return jsonify({
                "success": False,
                "error": f"Invalid token: {test_data.get('error', 'unknown error')}"
            }), 400

        team_name = test_data.get("team", "Slack")
        team_id = test_data.get("team_id", "")

        # Save connector
        db = get_db()
        try:
            connector = db.query(Connector).filter(
                Connector.tenant_id == g.tenant_id,
                Connector.connector_type == ConnectorType.SLACK
            ).first()

            if connector:
                connector.access_token = access_token
                connector.status = ConnectorStatus.CONNECTED
                connector.is_active = True  # Re-enable connector on reconnect
                connector.name = team_name
                connector.error_message = None
                connector.settings = {
                    "team_id": team_id,
                    "team_name": team_name,
                    "connected_via": "token"
                }
                connector.updated_at = utc_now()
            else:
                connector = Connector(
                    tenant_id=g.tenant_id,
                    user_id=g.user_id,
                    connector_type=ConnectorType.SLACK,
                    name=team_name,
                    status=ConnectorStatus.CONNECTED,
                    access_token=access_token,
                    settings={
                        "team_id": team_id,
                        "team_name": team_name,
                        "connected_via": "token"
                    }
                )
                db.add(connector)

            db.commit()

            return jsonify({
                "success": True,
                "message": f"Connected to {team_name}",
                "team_name": team_name
            })

        finally:
            db.close()

    except Exception as e:
        print(f"[Slack Token] Error: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@integration_bp.route('/slack/callback', methods=['GET', 'POST'])
def slack_callback():
    """
    Slack OAuth callback (GET) and Events webhook (POST) handler.

    POST: Handles Slack Events including url_verification challenge
    GET: Handles OAuth callback after user authorizes the app
    """
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

    # LOG EVERY REQUEST (for debugging event delivery)
    print(f"[Slack Callback] >>>>>> REQUEST RECEIVED method={request.method} content_type={request.content_type} content_length={request.content_length} remote_addr={request.remote_addr}", flush=True)
    print(f"[Slack Callback] >>>>>> Headers: X-Slack-Signature={request.headers.get('X-Slack-Signature', 'MISSING')[:30]}... X-Slack-Request-Timestamp={request.headers.get('X-Slack-Request-Timestamp', 'MISSING')}", flush=True)

    # Handle POST requests (Slack Events)
    if request.method == 'POST':
        try:
            raw_body = request.get_data(as_text=True)
            print(f"[Slack Events] Raw body length: {len(raw_body)}, first 200 chars: {raw_body[:200]}", flush=True)
            data = request.get_json(force=True, silent=True)
            if not data:
                print(f"[Slack Events] ERROR: Could not parse JSON from body", flush=True)
                return jsonify({'ok': True}), 200
            event_type = data.get('type')

            # Detailed logging for debugging
            print(f"[Slack Events] ========== INCOMING EVENT ==========", flush=True)
            print(f"[Slack Events] Type: {event_type}", flush=True)
            print(f"[Slack Events] Team ID: {data.get('team_id')}", flush=True)
            if data.get('event'):
                event_data = data.get('event', {})
                print(f"[Slack Events] Event subtype: {event_data.get('type')}", flush=True)
                print(f"[Slack Events] Channel: {event_data.get('channel')}", flush=True)
                print(f"[Slack Events] User: {event_data.get('user')}", flush=True)
                print(f"[Slack Events] Text: {event_data.get('text', '')[:100]}", flush=True)
            print(f"[Slack Events] ===================================", flush=True)

            # Handle URL verification challenge (MUST respond immediately)
            if event_type == 'url_verification':
                challenge = data.get('challenge', '')
                print(f"[Slack Events] Responding to challenge", flush=True)
                # Return challenge as plain text (Slack accepts both)
                return challenge, 200, {'Content-Type': 'text/plain'}

            # Handle event callbacks
            if event_type == 'event_callback':
                event = data.get('event', {})
                event_subtype = event.get('type')
                team_id = data.get('team_id')
                event_id = data.get('event_id')  # Unique ID for deduplication

                print(f"[Slack Events] Event: {event_subtype} from team: {team_id} (event_id: {event_id})", flush=True)

                # DEDUPLICATION: Skip if we already processed this event
                if _is_duplicate_event(event_id):
                    return jsonify({'ok': True})  # Return 200 to prevent more retries

                # CRITICAL FIX: Process in background thread to respond to Slack within 3 seconds
                # Slack retries if we don't respond quickly, causing duplicate messages
                def process_slack_event_async(team_id, event, event_subtype, event_id):
                    """Process Slack event in background thread"""
                    print(f"[Slack Events] ===== BACKGROUND THREAD STARTED =====", flush=True)
                    print(f"[Slack Events] team_id={team_id}, event_subtype={event_subtype}, event_id={event_id}", flush=True)
                    try:
                        from services.slack_bot_service import (
                            SlackBotService,
                            get_tenant_for_workspace,
                            get_bot_token_for_workspace
                        )

                        # Get tenant for this workspace
                        print(f"[Slack Events] Looking up tenant for team {team_id}...", flush=True)
                        tenant_id = get_tenant_for_workspace(team_id)
                        if not tenant_id:
                            print(f"[Slack Events] ERROR: No tenant found for workspace {team_id}", flush=True)
                            return

                        # Get bot token
                        print(f"[Slack Events] Looking up bot token for team {team_id}...", flush=True)
                        bot_token = get_bot_token_for_workspace(team_id)
                        if not bot_token:
                            print(f"[Slack Events] ERROR: No bot token for workspace {team_id}", flush=True)
                            return

                        print(f"[Slack Events] Creating SlackBotService for tenant {tenant_id[:8]}...", flush=True)

                        # Create bot service and handle event
                        bot_service = SlackBotService(bot_token)
                        print(f"[Slack Events] SlackBotService created, bot_user_id={bot_service.bot_user_id}", flush=True)

                        # Handle @mentions
                        if event_subtype == 'app_mention':
                            print(f"[Slack Events] Calling handle_app_mention...", flush=True)
                            bot_service.handle_app_mention(tenant_id, event)
                            print(f"[Slack Events] handle_app_mention completed", flush=True)

                        # Handle direct messages
                        elif event_subtype == 'message':
                            channel = event.get('channel', '')
                            if not event.get('bot_id') and channel.startswith('D'):
                                print(f"[Slack Events] Calling handle_message for DM...", flush=True)
                                bot_service.handle_message(tenant_id, event)
                                print(f"[Slack Events] handle_message completed", flush=True)
                            else:
                                print(f"[Slack Events] Skipping message: bot_id={event.get('bot_id')}, channel={channel}", flush=True)

                        print(f"[Slack Events] ===== BACKGROUND THREAD COMPLETED =====", flush=True)

                    except Exception as e:
                        import traceback
                        print(f"[Slack Events] ===== BACKGROUND THREAD ERROR =====", flush=True)
                        print(f"[Slack Events] Error: {type(e).__name__}: {e}", flush=True)
                        traceback.print_exc()

                # Start background thread and return immediately
                thread = threading.Thread(
                    target=process_slack_event_async,
                    args=(team_id, event, event_subtype, event_id)
                )
                thread.daemon = True  # Don't block shutdown
                thread.start()

                print(f"[Slack Events] Spawned background thread, returning 200 immediately", flush=True)
                return jsonify({'ok': True})  # Return immediately to Slack!

            return jsonify({'ok': True})

        except Exception as e:
            print(f"[Slack Events] Error: {e}", flush=True)
            return jsonify({'ok': True})  # Always return 200 to prevent retries

    # Handle GET requests (OAuth callback)
    try:
        import requests

        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')

        print(f"[Slack Callback] code={code[:20] if code else None}..., state={state}, error={error}")

        if error:
            return redirect(f"{FRONTEND_URL}/integrations?error={error}")

        if not code or not state:
            return redirect(f"{FRONTEND_URL}/integrations?error=missing_params")

        # Verify JWT-based state
        state_data, error_msg = verify_oauth_state(state)
        if error_msg or not state_data or state_data.get("connector_type") != "slack":
            print(f"[Slack Callback] Invalid state: {error_msg}")
            return redirect(f"{FRONTEND_URL}/integrations?error=invalid_state")

        # Exchange code for tokens
        client_id = os.getenv("SLACK_CLIENT_ID", "")
        client_secret = os.getenv("SLACK_CLIENT_SECRET", "")
        redirect_uri = os.getenv(
            "SLACK_REDIRECT_URI",
            "http://localhost:5003/api/integrations/slack/callback"
        )

        print(f"[Slack Callback] Exchanging code for token with redirect_uri={redirect_uri}")

        response = requests.post(
            "https://slack.com/api/oauth.v2.access",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri
            }
        )

        data = response.json()
        print(f"[Slack Callback] Token response: ok={data.get('ok')}, error={data.get('error')}")

        if not data.get("ok"):
            error_msg = data.get('error', 'unknown')
            print(f"[Slack Callback] OAuth failed: {error_msg}")
            return redirect(f"{FRONTEND_URL}/integrations?error={error_msg}")

        # Save connector
        db = get_db()
        try:
            connector = db.query(Connector).filter(
                Connector.tenant_id == state_data["tenant_id"],
                Connector.connector_type == ConnectorType.SLACK
            ).first()

            access_token = data.get("access_token")
            team_name = data.get("team", {}).get("name", "Slack")
            is_first_connection = connector is None

            if connector:
                connector.access_token = access_token
                connector.status = ConnectorStatus.CONNECTED
                connector.is_active = True  # Re-enable connector on reconnect
                connector.name = team_name
                connector.error_message = None
                connector.settings = {
                    "team_id": data.get("team", {}).get("id"),
                    "team_name": team_name,
                    "bot_user_id": data.get("bot_user_id")
                }
                connector.updated_at = utc_now()
            else:
                connector = Connector(
                    tenant_id=state_data["tenant_id"],
                    user_id=state_data["user_id"],
                    connector_type=ConnectorType.SLACK,
                    name=team_name,
                    status=ConnectorStatus.CONNECTED,
                    access_token=access_token,
                    token_scopes=data.get("scope", "").split(","),
                    settings={
                        "team_id": data.get("team", {}).get("id"),
                        "team_name": team_name,
                        "bot_user_id": data.get("bot_user_id")
                    }
                )
                db.add(connector)

            db.commit()
            print(f"[Slack Callback] Successfully saved connector for team: {team_name}")

            # Auto-sync on first connection
            if is_first_connection:
                connector_id = connector.id
                tenant_id = state_data["tenant_id"]
                user_id = state_data["user_id"]

                def run_initial_sync():
                    _run_connector_sync(
                        connector_id=connector_id,
                        connector_type="slack",
                        since=None,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        full_sync=True
                    )

                thread = threading.Thread(target=run_initial_sync)
                thread.daemon = True
                thread.start()

                print(f"[Slack Callback] Started auto-sync for first-time connection")

            return redirect(f"{FRONTEND_URL}/integrations?success=slack")

        finally:
            db.close()

    except Exception as e:
        print(f"[Slack Callback] Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return redirect(f"{FRONTEND_URL}/integrations?error={quote(str(e))}")


# ============================================================================
# BOX INTEGRATION
# ============================================================================

@integration_bp.route('/box/auth', methods=['GET'])
@require_auth
def box_auth():
    """
    Start Box OAuth flow.
    """
    try:
        print("[BoxAuth] Starting Box OAuth flow...")
        from connectors.box_connector import BoxConnector

        # Generate JWT-based state (works across multiple workers)
        redirect_uri = os.getenv(
            "BOX_REDIRECT_URI",
            "http://localhost:5003/api/integrations/box/callback"
        )
        print(f"[BoxAuth] Redirect URI: {redirect_uri}")

        state = create_oauth_state(
            tenant_id=g.tenant_id,
            user_id=g.user_id,
            connector_type="box",
            extra_data={"redirect_uri": redirect_uri}
        )
        print(f"[BoxAuth] JWT state created for tenant: {g.tenant_id}")

        # Get auth URL
        print("[BoxAuth] Getting auth URL from BoxConnector...")
        auth_url = BoxConnector.get_auth_url(redirect_uri, state)
        print(f"[BoxAuth] Auth URL generated: {auth_url[:100]}...")

        return jsonify({
            "success": True,
            "auth_url": auth_url,
            "state": state
        })

    except ImportError as e:
        print(f"[BoxAuth] ImportError: {e}")
        return jsonify({
            "success": False,
            "error": "Box SDK not installed. Run: pip install boxsdk"
        }), 500
    except Exception as e:
        import traceback
        print(f"[BoxAuth] Exception: {e}")
        print(f"[BoxAuth] Traceback: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@integration_bp.route('/box/callback', methods=['GET'])
def box_callback():
    """
    Box OAuth callback handler.
    """
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

    try:
        from connectors.box_connector import BoxConnector

        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')

        if error:
            return redirect(f"{FRONTEND_URL}/integrations?error={error}")

        if not code or not state:
            return redirect(f"{FRONTEND_URL}/integrations?error=missing_params")

        # Verify JWT-based state
        state_data, error = verify_oauth_state(state)
        if error or not state_data or state_data.get("connector_type") != "box":
            print(f"[BoxCallback] Invalid state: {error}")
            return redirect(f"{FRONTEND_URL}/integrations?error=invalid_state")

        # Exchange code for tokens
        redirect_uri = state_data.get("data", {}).get("redirect_uri")
        tokens, error = BoxConnector.exchange_code_for_tokens(code, redirect_uri)

        if error:
            return redirect(f"{FRONTEND_URL}/integrations?error={error}")

        # Save connector
        db = get_db()
        try:
            connector = db.query(Connector).filter(
                Connector.tenant_id == state_data["tenant_id"],
                Connector.connector_type == ConnectorType.BOX
            ).first()

            is_first_connection = connector is None

            if connector:
                connector.access_token = tokens["access_token"]
                connector.refresh_token = tokens["refresh_token"]
                connector.status = ConnectorStatus.CONNECTED
                connector.is_active = True  # Re-enable connector on reconnect
                connector.error_message = None
                connector.updated_at = utc_now()
            else:
                connector = Connector(
                    tenant_id=state_data["tenant_id"],
                    user_id=state_data["user_id"],
                    connector_type=ConnectorType.BOX,
                    name="Box",
                    status=ConnectorStatus.CONNECTED,
                    access_token=tokens["access_token"],
                    refresh_token=tokens["refresh_token"]
                )
                db.add(connector)

            db.commit()

            # Auto-sync on first connection
            if is_first_connection:
                connector_id = connector.id
                tenant_id = state_data["tenant_id"]
                user_id = state_data["user_id"]

                def run_initial_sync():
                    _run_connector_sync(
                        connector_id=connector_id,
                        connector_type="box",
                        since=None,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        full_sync=True
                    )

                thread = threading.Thread(target=run_initial_sync)
                thread.daemon = True
                thread.start()

                print(f"[Box Callback] Started auto-sync for first-time connection")

            return redirect(f"{FRONTEND_URL}/integrations?success=box")

        finally:
            db.close()

    except Exception as e:
        return redirect(f"{FRONTEND_URL}/integrations?error={quote(str(e))}")


@integration_bp.route('/box/folders', methods=['GET'])
@require_auth
def box_folders():
    """
    Get Box folder structure for configuration.
    """
    try:
        from connectors.box_connector import BoxConnector

        db = get_db()
        try:
            connector = db.query(Connector).filter(
                Connector.tenant_id == g.tenant_id,
                Connector.connector_type == ConnectorType.BOX,
                Connector.status == ConnectorStatus.CONNECTED
            ).first()

            if not connector:
                return jsonify({
                    "success": False,
                    "error": "Box not connected"
                }), 400

            # Create connector instance and get folder tree
            from connectors.base_connector import ConnectorConfig

            config = ConnectorConfig(
                connector_type="box",
                credentials={
                    "access_token": connector.access_token,
                    "refresh_token": connector.refresh_token
                },
                settings=connector.settings or {}
            )

            box = BoxConnector(config)

            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                connected = loop.run_until_complete(box.connect())
                if not connected:
                    return jsonify({
                        "success": False,
                        "error": "Failed to connect to Box"
                    }), 400

                folder_id = request.args.get('folder_id', '0')
                depth = int(request.args.get('depth', '2'))

                folders = loop.run_until_complete(
                    box.get_folder_structure(folder_id, depth)
                )

                return jsonify({
                    "success": True,
                    "folders": folders
                })

            finally:
                loop.close()

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# GITHUB INTEGRATION
# ============================================================================

@integration_bp.route('/github/auth', methods=['GET'])
@require_auth
def github_auth():
    """
    Start GitHub OAuth flow.
    """
    try:
        print("[GitHubAuth] Starting GitHub OAuth flow...")

        client_id = os.getenv("GITHUB_CLIENT_ID", "")

        # Auto-detect redirect URI based on request URL
        # This handles both localhost and production (Render) automatically
        if os.getenv("GITHUB_REDIRECT_URI"):
            redirect_uri = os.getenv("GITHUB_REDIRECT_URI")
        else:
            # Build from request URL
            host = request.host_url.rstrip('/')
            redirect_uri = f"{host}/api/integrations/github/callback"

        print(f"[GitHubAuth] Request host: {request.host_url}")

        if not client_id:
            return jsonify({
                "success": False,
                "error": "GitHub Client ID not configured. Please set GITHUB_CLIENT_ID in environment variables."
            }), 500

        print(f"[GitHubAuth] Client ID: {client_id[:10]}...")
        print(f"[GitHubAuth] Redirect URI: {redirect_uri}")

        # Create JWT state
        state = create_oauth_state(
            tenant_id=g.tenant_id,
            user_id=g.user_id,
            connector_type="github",
            extra_data={"redirect_uri": redirect_uri}
        )
        print(f"[GitHubAuth] JWT state created for tenant: {g.tenant_id}")

        # Build GitHub OAuth URL
        auth_url = (
            f"https://github.com/login/oauth/authorize"
            f"?client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&state={state}"
            f"&scope=repo,read:user,read:org"  # Scopes for reading repos and user info
        )

        print(f"[GitHubAuth] Auth URL generated: {auth_url[:100]}...")

        return jsonify({
            "success": True,
            "auth_url": auth_url,
            "state": state
        })

    except Exception as e:
        import traceback
        print(f"[GitHubAuth] Exception: {e}")
        print(f"[GitHubAuth] Traceback: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@integration_bp.route('/github/callback', methods=['GET'])
def github_callback():
    """
    GitHub OAuth callback handler.
    """
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

    try:
        import requests

        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')

        print(f"[GitHub Callback] code={code[:20] if code else None}..., state={state}, error={error}")

        if error:
            return redirect(f"{FRONTEND_URL}/integrations?error={error}")

        if not code or not state:
            return redirect(f"{FRONTEND_URL}/integrations?error=missing_params")

        # Verify JWT state
        state_data, error_msg = verify_oauth_state(state)
        if error_msg or not state_data or state_data.get("connector_type") != "github":
            print(f"[GitHub Callback] Invalid state: {error_msg}")
            return redirect(f"{FRONTEND_URL}/integrations?error=invalid_state")

        tenant_id = state_data.get("tenant_id")
        user_id = state_data.get("user_id")
        redirect_uri = state_data.get("data", {}).get("redirect_uri")

        print(f"[GitHub Callback] JWT state verified for tenant: {tenant_id}")

        # Exchange code for token
        client_id = os.getenv("GITHUB_CLIENT_ID", "")
        client_secret = os.getenv("GITHUB_CLIENT_SECRET", "")

        print(f"[GitHub Callback] Exchanging code for token...")

        response = requests.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri
            },
            headers={"Accept": "application/json"}
        )

        data = response.json()
        print(f"[GitHub Callback] Token response: {list(data.keys())}")

        if "error" in data:
            error_msg = data.get('error_description', data.get('error', 'unknown'))
            print(f"[GitHub Callback] OAuth failed: {error_msg}")
            return redirect(f"{FRONTEND_URL}/integrations?error={error_msg}")

        access_token = data.get("access_token")
        if not access_token:
            return redirect(f"{FRONTEND_URL}/integrations?error=no_access_token")

        # Get user info
        user_response = requests.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github+json"
            }
        )
        user_data = user_response.json()
        github_username = user_data.get("login", "GitHub")

        # Save connector
        db = get_db()
        try:
            connector = db.query(Connector).filter(
                Connector.tenant_id == tenant_id,
                Connector.connector_type == ConnectorType.GITHUB
            ).first()

            is_first_connection = connector is None

            if connector:
                connector.access_token = access_token
                connector.status = ConnectorStatus.CONNECTED
                connector.is_active = True
                connector.name = f"GitHub ({github_username})"
                connector.error_message = None
                connector.settings = {
                    "username": github_username,
                    "user_id": user_data.get("id")
                }
                connector.updated_at = utc_now()
            else:
                connector = Connector(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    connector_type=ConnectorType.GITHUB,
                    name=f"GitHub ({github_username})",
                    status=ConnectorStatus.CONNECTED,
                    access_token=access_token,
                    token_scopes=data.get("scope", "").split(","),
                    settings={
                        "username": github_username,
                        "user_id": user_data.get("id")
                    }
                )
                db.add(connector)

            db.commit()
            print(f"[GitHub Callback] Successfully saved connector for user: {github_username}")

            # Auto-sync on first connection
            if is_first_connection:
                connector_id = connector.id
                sync_tenant_id = tenant_id
                sync_user_id = user_id

                def run_initial_sync():
                    _run_connector_sync(
                        connector_id=connector_id,
                        connector_type="github",
                        since=None,
                        tenant_id=sync_tenant_id,
                        user_id=sync_user_id,
                        full_sync=True
                    )

                thread = threading.Thread(target=run_initial_sync)
                thread.daemon = True
                thread.start()

                print(f"[GitHub Callback] Started auto-sync for first-time connection")

            return redirect(f"{FRONTEND_URL}/integrations?success=github")

        finally:
            db.close()

    except Exception as e:
        print(f"[GitHub Callback] Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return redirect(f"{FRONTEND_URL}/integrations?error={quote(str(e))}")


# ============================================================================
# ONEDRIVE (MICROSOFT 365) INTEGRATION
# ============================================================================

@integration_bp.route('/onedrive/auth', methods=['GET'])
@require_auth
def onedrive_auth():
    """
    Start OneDrive/Microsoft 365 OAuth flow.
    """
    try:
        print("[OneDriveAuth] Starting OneDrive OAuth flow...")
        from connectors.onedrive_connector import OneDriveConnector

        redirect_uri = os.getenv(
            "MICROSOFT_REDIRECT_URI",
            "http://localhost:5003/api/integrations/onedrive/callback"
        )
        print(f"[OneDriveAuth] Redirect URI: {redirect_uri}")

        # Create JWT state (multi-worker safe)
        state = create_oauth_state(
            tenant_id=g.tenant_id,
            user_id=g.user_id,
            connector_type="onedrive",
            extra_data={"redirect_uri": redirect_uri}
        )
        print(f"[OneDriveAuth] JWT state created for tenant: {g.tenant_id}")

        # Get auth URL
        print("[OneDriveAuth] Getting auth URL from OneDriveConnector...")
        auth_url = OneDriveConnector.get_auth_url(redirect_uri, state)
        print(f"[OneDriveAuth] Auth URL generated: {auth_url[:100]}...")

        return jsonify({
            "success": True,
            "auth_url": auth_url,
            "state": state
        })

    except ImportError as e:
        print(f"[OneDriveAuth] ImportError: {e}")
        return jsonify({
            "success": False,
            "error": "MSAL not installed. Run: pip install msal"
        }), 500
    except Exception as e:
        import traceback
        print(f"[OneDriveAuth] Exception: {e}")
        print(f"[OneDriveAuth] Traceback: {traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@integration_bp.route('/onedrive/callback', methods=['GET'])
def onedrive_callback():
    """
    OneDrive OAuth callback handler.
    """
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

    try:
        from connectors.onedrive_connector import OneDriveConnector

        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')

        if error:
            return safe_error_redirect(f"{FRONTEND_URL}/integrations", error)

        if not code or not state:
            return safe_error_redirect(f"{FRONTEND_URL}/integrations", "missing_params")

        # Verify JWT state (multi-worker safe)
        state_data, error_msg = verify_oauth_state(state)
        if error_msg or not state_data or state_data.get("connector_type") != "onedrive":
            print(f"[OneDrive Callback] Invalid state: {error_msg}")
            return safe_error_redirect(f"{FRONTEND_URL}/integrations", error_msg or "invalid_state")

        tenant_id = state_data.get("tenant_id")
        user_id = state_data.get("user_id")
        redirect_uri = state_data.get("data", {}).get("redirect_uri")

        # Exchange code for tokens
        tokens, error = OneDriveConnector.exchange_code_for_tokens(code, redirect_uri)

        if error:
            return safe_error_redirect(f"{FRONTEND_URL}/integrations", error)

        # Save connector
        db = get_db()
        try:
            connector = db.query(Connector).filter(
                Connector.tenant_id == tenant_id,
                Connector.connector_type == ConnectorType.ONEDRIVE
            ).first()

            is_first_connection = connector is None

            if connector:
                connector.access_token = tokens["access_token"]
                connector.refresh_token = tokens["refresh_token"]
                connector.status = ConnectorStatus.CONNECTED
                connector.is_active = True
                connector.error_message = None
                connector.updated_at = utc_now()
            else:
                connector = Connector(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    connector_type=ConnectorType.ONEDRIVE,
                    name="OneDrive",
                    status=ConnectorStatus.CONNECTED,
                    access_token=tokens["access_token"],
                    refresh_token=tokens["refresh_token"]
                )
                db.add(connector)

            db.commit()
            print(f"[OneDrive Callback] Successfully saved connector")

            # Auto-sync DISABLED - user should manually trigger sync
            # if is_first_connection:
            #     connector_id = connector.id
            #     sync_tenant_id = tenant_id
            #     sync_user_id = user_id
            #
            #     def run_initial_sync():
            #         _run_connector_sync(
            #             connector_id=connector_id,
            #             connector_type="onedrive",
            #             since=None,
            #             tenant_id=sync_tenant_id,
            #             user_id=sync_user_id,
            #             full_sync=True
            #         )
            #
            #     thread = threading.Thread(target=run_initial_sync)
            #     thread.daemon = True
            #     thread.start()
            #
            #     print(f"[OneDrive Callback] Started auto-sync for first-time connection")

            return redirect(f"{FRONTEND_URL}/integrations?success=onedrive")

        finally:
            db.close()

    except Exception as e:
        return safe_error_redirect(f"{FRONTEND_URL}/integrations", str(e))


# ============================================================================
# NOTION INTEGRATION
# ============================================================================

@integration_bp.route('/notion/auth', methods=['GET'])
@require_auth
def notion_auth():
    """Start Notion OAuth flow."""
    try:
        from connectors.notion_connector import NotionConnector

        redirect_uri = _get_oauth_redirect_uri('notion')

        state = create_oauth_state(
            tenant_id=g.tenant_id,
            user_id=g.user_id,
            connector_type="notion",
            extra_data={"redirect_uri": redirect_uri}
        )

        auth_url = NotionConnector.get_auth_url(redirect_uri, state)

        return jsonify({
            "success": True,
            "auth_url": auth_url,
            "state": state
        })

    except ImportError as e:
        return jsonify({
            "success": False,
            "error": "Notion SDK not installed. Run: pip install notion-client"
        }), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@integration_bp.route('/notion/callback', methods=['GET'])
def notion_callback():
    """Notion OAuth callback handler."""
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

    try:
        from connectors.notion_connector import NotionConnector

        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')

        if error:
            return redirect(f"{FRONTEND_URL}/integrations?error={error}")

        if not code or not state:
            return redirect(f"{FRONTEND_URL}/integrations?error=missing_params")

        state_data, error = verify_oauth_state(state)
        if error or not state_data or state_data.get("connector_type") != "notion":
            return redirect(f"{FRONTEND_URL}/integrations?error=invalid_state")

        redirect_uri = state_data.get("data", {}).get("redirect_uri")
        tokens = NotionConnector.exchange_code(code, redirect_uri)

        db = get_db()
        try:
            connector = db.query(Connector).filter(
                Connector.tenant_id == state_data["tenant_id"],
                Connector.connector_type == ConnectorType.NOTION
            ).first()

            is_first_connection = connector is None

            if connector:
                connector.access_token = tokens["access_token"]
                connector.status = ConnectorStatus.CONNECTED
                connector.is_active = True
                connector.error_message = None
                connector.updated_at = utc_now()
            else:
                connector = Connector(
                    tenant_id=state_data["tenant_id"],
                    user_id=state_data["user_id"],
                    connector_type=ConnectorType.NOTION,
                    name="Notion",
                    status=ConnectorStatus.CONNECTED,
                    access_token=tokens["access_token"]
                )
                db.add(connector)

            db.commit()

            if is_first_connection:
                connector_id = connector.id
                tenant_id = state_data["tenant_id"]
                user_id = state_data["user_id"]

                def run_initial_sync():
                    _run_connector_sync(
                        connector_id=connector_id,
                        connector_type="notion",
                        since=None,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        full_sync=True
                    )

                thread = threading.Thread(target=run_initial_sync)
                thread.daemon = True
                thread.start()

            return redirect(f"{FRONTEND_URL}/integrations?success=notion")

        finally:
            db.close()

    except Exception as e:
        return redirect(f"{FRONTEND_URL}/integrations?error={quote(str(e))}")


# ============================================================================
# GOOGLE DRIVE INTEGRATION
# ============================================================================

@integration_bp.route('/gdrive/auth', methods=['GET'])
@require_auth
def gdrive_auth():
    """Start Google Drive OAuth flow."""
    try:
        from connectors.gdrive_connector import GDriveConnector

        redirect_uri = os.getenv(
            "GDRIVE_REDIRECT_URI",
            "http://localhost:5003/api/integrations/gdrive/callback"
        )

        state = create_oauth_state(
            tenant_id=g.tenant_id,
            user_id=g.user_id,
            connector_type="gdrive",
            extra_data={"redirect_uri": redirect_uri}
        )

        auth_url = GDriveConnector.get_auth_url(redirect_uri, state)

        return jsonify({
            "success": True,
            "auth_url": auth_url,
            "state": state
        })

    except ImportError as e:
        return jsonify({
            "success": False,
            "error": "Google API SDK not installed"
        }), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@integration_bp.route('/gdrive/callback', methods=['GET'])
def gdrive_callback():
    """Google Drive OAuth callback handler."""
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

    try:
        from connectors.gdrive_connector import GDriveConnector

        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')

        if error:
            return redirect(f"{FRONTEND_URL}/integrations?error={error}")

        if not code or not state:
            return redirect(f"{FRONTEND_URL}/integrations?error=missing_params")

        state_data, error = verify_oauth_state(state)
        if error or not state_data or state_data.get("connector_type") != "gdrive":
            return redirect(f"{FRONTEND_URL}/integrations?error=invalid_state")

        redirect_uri = state_data.get("data", {}).get("redirect_uri")
        tokens = GDriveConnector.exchange_code(code, redirect_uri)

        db = get_db()
        try:
            connector = db.query(Connector).filter(
                Connector.tenant_id == state_data["tenant_id"],
                Connector.connector_type == ConnectorType.GOOGLE_DRIVE
            ).first()

            is_first_connection = connector is None

            if connector:
                connector.access_token = tokens["access_token"]
                connector.refresh_token = tokens.get("refresh_token")
                connector.status = ConnectorStatus.CONNECTED
                connector.is_active = True
                connector.error_message = None
                connector.updated_at = utc_now()
            else:
                connector = Connector(
                    tenant_id=state_data["tenant_id"],
                    user_id=state_data["user_id"],
                    connector_type=ConnectorType.GOOGLE_DRIVE,
                    name="Google Drive",
                    status=ConnectorStatus.CONNECTED,
                    access_token=tokens["access_token"],
                    refresh_token=tokens.get("refresh_token")
                )
                db.add(connector)

            db.commit()

            if is_first_connection:
                connector_id = connector.id
                tenant_id = state_data["tenant_id"]
                user_id = state_data["user_id"]

                def run_initial_sync():
                    _run_connector_sync(
                        connector_id=connector_id,
                        connector_type="gdrive",
                        since=None,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        full_sync=True
                    )

                thread = threading.Thread(target=run_initial_sync)
                thread.daemon = True
                thread.start()

            return redirect(f"{FRONTEND_URL}/integrations?success=gdrive")

        finally:
            db.close()

    except Exception as e:
        return redirect(f"{FRONTEND_URL}/integrations?error={quote(str(e))}")


# ============================================================================
# GOOGLE DOCS INTEGRATION
# ============================================================================

@integration_bp.route('/gdocs/auth', methods=['GET'])
@require_auth
def gdocs_auth():
    """Start Google Docs OAuth flow."""
    try:
        from connectors.gdocs_connector import GDocsConnector
        redirect_uri = os.getenv("GDOCS_REDIRECT_URI",
            "http://localhost:5003/api/integrations/gdocs/callback")
        state = create_oauth_state(
            tenant_id=g.tenant_id, user_id=g.user_id,
            connector_type="gdocs", extra_data={"redirect_uri": redirect_uri}
        )
        auth_url = GDocsConnector.get_auth_url(redirect_uri, state)
        return jsonify({"success": True, "auth_url": auth_url, "state": state})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@integration_bp.route('/gdocs/callback', methods=['GET'])
def gdocs_callback():
    """Google Docs OAuth callback handler."""
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
    try:
        from connectors.gdocs_connector import GDocsConnector
        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')
        if error:
            return redirect(f"{FRONTEND_URL}/integrations?error={error}")
        if not code or not state:
            return redirect(f"{FRONTEND_URL}/integrations?error=missing_params")

        state_data, error = verify_oauth_state(state)
        if error or not state_data or state_data.get("connector_type") != "gdocs":
            return redirect(f"{FRONTEND_URL}/integrations?error=invalid_state")

        redirect_uri = state_data.get("data", {}).get("redirect_uri")
        tokens = GDocsConnector.exchange_code(code, redirect_uri)

        db = get_db()
        try:
            connector = db.query(Connector).filter(
                Connector.tenant_id == state_data["tenant_id"],
                Connector.connector_type == ConnectorType.GOOGLE_DOCS
            ).first()
            is_first = connector is None
            if connector:
                connector.access_token = tokens["access_token"]
                connector.refresh_token = tokens.get("refresh_token")
                connector.status = ConnectorStatus.CONNECTED
                connector.is_active = True
                connector.error_message = None
                connector.updated_at = utc_now()
            else:
                connector = Connector(
                    tenant_id=state_data["tenant_id"], user_id=state_data["user_id"],
                    connector_type=ConnectorType.GOOGLE_DOCS, name="Google Docs",
                    status=ConnectorStatus.CONNECTED,
                    access_token=tokens["access_token"], refresh_token=tokens.get("refresh_token")
                )
                db.add(connector)
            db.commit()
            if is_first:
                cid, tid, uid = connector.id, state_data["tenant_id"], state_data["user_id"]
                def run_sync():
                    _run_connector_sync(connector_id=cid, connector_type="gdocs", since=None, tenant_id=tid, user_id=uid, full_sync=True)
                thread = threading.Thread(target=run_sync, daemon=True)
                thread.start()
            return redirect(f"{FRONTEND_URL}/integrations?success=gdocs")
        finally:
            db.close()
    except Exception as e:
        return redirect(f"{FRONTEND_URL}/integrations?error={quote(str(e))}")


# ============================================================================
# GOOGLE SHEETS INTEGRATION
# ============================================================================

@integration_bp.route('/gsheets/auth', methods=['GET'])
@require_auth
def gsheets_auth():
    """Start Google Sheets OAuth flow."""
    try:
        from connectors.gsheets_connector import GSheetsConnector
        redirect_uri = os.getenv("GSHEETS_REDIRECT_URI",
            "http://localhost:5003/api/integrations/gsheets/callback")
        state = create_oauth_state(
            tenant_id=g.tenant_id, user_id=g.user_id,
            connector_type="gsheets", extra_data={"redirect_uri": redirect_uri}
        )
        auth_url = GSheetsConnector.get_auth_url(redirect_uri, state)
        return jsonify({"success": True, "auth_url": auth_url, "state": state})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@integration_bp.route('/gsheets/callback', methods=['GET'])
def gsheets_callback():
    """Google Sheets OAuth callback handler."""
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
    try:
        from connectors.gsheets_connector import GSheetsConnector
        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')
        if error:
            return redirect(f"{FRONTEND_URL}/integrations?error={error}")
        if not code or not state:
            return redirect(f"{FRONTEND_URL}/integrations?error=missing_params")

        state_data, error = verify_oauth_state(state)
        if error or not state_data or state_data.get("connector_type") != "gsheets":
            return redirect(f"{FRONTEND_URL}/integrations?error=invalid_state")

        redirect_uri = state_data.get("data", {}).get("redirect_uri")
        tokens = GSheetsConnector.exchange_code(code, redirect_uri)

        db = get_db()
        try:
            connector = db.query(Connector).filter(
                Connector.tenant_id == state_data["tenant_id"],
                Connector.connector_type == ConnectorType.GOOGLE_SHEETS
            ).first()
            is_first = connector is None
            if connector:
                connector.access_token = tokens["access_token"]
                connector.refresh_token = tokens.get("refresh_token")
                connector.status = ConnectorStatus.CONNECTED
                connector.is_active = True
                connector.error_message = None
                connector.updated_at = utc_now()
            else:
                connector = Connector(
                    tenant_id=state_data["tenant_id"], user_id=state_data["user_id"],
                    connector_type=ConnectorType.GOOGLE_SHEETS, name="Google Sheets",
                    status=ConnectorStatus.CONNECTED,
                    access_token=tokens["access_token"], refresh_token=tokens.get("refresh_token")
                )
                db.add(connector)
            db.commit()
            if is_first:
                cid, tid, uid = connector.id, state_data["tenant_id"], state_data["user_id"]
                def run_sync():
                    _run_connector_sync(connector_id=cid, connector_type="gsheets", since=None, tenant_id=tid, user_id=uid, full_sync=True)
                thread = threading.Thread(target=run_sync, daemon=True)
                thread.start()
            return redirect(f"{FRONTEND_URL}/integrations?success=gsheets")
        finally:
            db.close()
    except Exception as e:
        return redirect(f"{FRONTEND_URL}/integrations?error={quote(str(e))}")


# ============================================================================
# GOOGLE SLIDES INTEGRATION
# ============================================================================

@integration_bp.route('/gslides/auth', methods=['GET'])
@require_auth
def gslides_auth():
    """Start Google Slides OAuth flow."""
    try:
        from connectors.gslides_connector import GSlidesConnector
        redirect_uri = os.getenv("GSLIDES_REDIRECT_URI",
            "http://localhost:5003/api/integrations/gslides/callback")
        state = create_oauth_state(
            tenant_id=g.tenant_id, user_id=g.user_id,
            connector_type="gslides", extra_data={"redirect_uri": redirect_uri}
        )
        auth_url = GSlidesConnector.get_auth_url(redirect_uri, state)
        return jsonify({"success": True, "auth_url": auth_url, "state": state})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@integration_bp.route('/gslides/callback', methods=['GET'])
def gslides_callback():
    """Google Slides OAuth callback handler."""
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
    try:
        from connectors.gslides_connector import GSlidesConnector
        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')
        if error:
            return redirect(f"{FRONTEND_URL}/integrations?error={error}")
        if not code or not state:
            return redirect(f"{FRONTEND_URL}/integrations?error=missing_params")

        state_data, error = verify_oauth_state(state)
        if error or not state_data or state_data.get("connector_type") != "gslides":
            return redirect(f"{FRONTEND_URL}/integrations?error=invalid_state")

        redirect_uri = state_data.get("data", {}).get("redirect_uri")
        tokens = GSlidesConnector.exchange_code(code, redirect_uri)

        db = get_db()
        try:
            connector = db.query(Connector).filter(
                Connector.tenant_id == state_data["tenant_id"],
                Connector.connector_type == ConnectorType.GOOGLE_SLIDES
            ).first()
            is_first = connector is None
            if connector:
                connector.access_token = tokens["access_token"]
                connector.refresh_token = tokens.get("refresh_token")
                connector.status = ConnectorStatus.CONNECTED
                connector.is_active = True
                connector.error_message = None
                connector.updated_at = utc_now()
            else:
                connector = Connector(
                    tenant_id=state_data["tenant_id"], user_id=state_data["user_id"],
                    connector_type=ConnectorType.GOOGLE_SLIDES, name="Google Slides",
                    status=ConnectorStatus.CONNECTED,
                    access_token=tokens["access_token"], refresh_token=tokens.get("refresh_token")
                )
                db.add(connector)
            db.commit()
            if is_first:
                cid, tid, uid = connector.id, state_data["tenant_id"], state_data["user_id"]
                def run_sync():
                    _run_connector_sync(connector_id=cid, connector_type="gslides", since=None, tenant_id=tid, user_id=uid, full_sync=True)
                thread = threading.Thread(target=run_sync, daemon=True)
                thread.start()
            return redirect(f"{FRONTEND_URL}/integrations?success=gslides")
        finally:
            db.close()
    except Exception as e:
        return redirect(f"{FRONTEND_URL}/integrations?error={quote(str(e))}")


# ============================================================================
# GOOGLE CALENDAR INTEGRATION
# ============================================================================

@integration_bp.route('/gcalendar/auth', methods=['GET'])
@require_auth
def gcalendar_auth():
    """Start Google Calendar OAuth flow."""
    try:
        from connectors.gcalendar_connector import GCalendarConnector
        redirect_uri = os.getenv("GCALENDAR_REDIRECT_URI",
            "http://localhost:5003/api/integrations/gcalendar/callback")
        state = create_oauth_state(
            tenant_id=g.tenant_id, user_id=g.user_id,
            connector_type="gcalendar", extra_data={"redirect_uri": redirect_uri}
        )
        auth_url = GCalendarConnector.get_auth_url(redirect_uri, state)
        return jsonify({"success": True, "auth_url": auth_url, "state": state})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@integration_bp.route('/gcalendar/callback', methods=['GET'])
def gcalendar_callback():
    """Google Calendar OAuth callback handler."""
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
    try:
        from connectors.gcalendar_connector import GCalendarConnector
        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')
        if error:
            return redirect(f"{FRONTEND_URL}/integrations?error={error}")
        if not code or not state:
            return redirect(f"{FRONTEND_URL}/integrations?error=missing_params")

        state_data, error = verify_oauth_state(state)
        if error or not state_data or state_data.get("connector_type") != "gcalendar":
            return redirect(f"{FRONTEND_URL}/integrations?error=invalid_state")

        redirect_uri = state_data.get("data", {}).get("redirect_uri")
        tokens = GCalendarConnector.exchange_code(code, redirect_uri)

        db = get_db()
        try:
            connector = db.query(Connector).filter(
                Connector.tenant_id == state_data["tenant_id"],
                Connector.connector_type == ConnectorType.GOOGLE_CALENDAR
            ).first()
            is_first = connector is None
            if connector:
                connector.access_token = tokens["access_token"]
                connector.refresh_token = tokens.get("refresh_token")
                connector.status = ConnectorStatus.CONNECTED
                connector.is_active = True
                connector.error_message = None
                connector.updated_at = utc_now()
            else:
                connector = Connector(
                    tenant_id=state_data["tenant_id"], user_id=state_data["user_id"],
                    connector_type=ConnectorType.GOOGLE_CALENDAR, name="Google Calendar",
                    status=ConnectorStatus.CONNECTED,
                    access_token=tokens["access_token"], refresh_token=tokens.get("refresh_token")
                )
                db.add(connector)
            db.commit()
            if is_first:
                cid, tid, uid = connector.id, state_data["tenant_id"], state_data["user_id"]
                def run_sync():
                    _run_connector_sync(connector_id=cid, connector_type="gcalendar", since=None, tenant_id=tid, user_id=uid, full_sync=True)
                thread = threading.Thread(target=run_sync, daemon=True)
                thread.start()
            return redirect(f"{FRONTEND_URL}/integrations?success=gcalendar")
        finally:
            db.close()
    except Exception as e:
        return redirect(f"{FRONTEND_URL}/integrations?error={quote(str(e))}")


# ============================================================================
# PUBMED INTEGRATION
# ============================================================================

@integration_bp.route('/pubmed/configure', methods=['POST'])
@require_auth
def pubmed_configure():
    """
    Configure PubMed search parameters.

    Request body:
    {
        "search_query": "NICU[Title] AND outcomes",  // Required
        "max_results": 100,  // Optional, default 100
        "date_range_years": 5,  // Optional, default 5 (0 = all time)
        "include_abstracts_only": true,  // Optional, default true
        "api_key": "your_ncbi_api_key"  // Optional
    }
    """
    try:
        data = request.get_json()
        search_query = data.get("search_query", "").strip()

        if not search_query:
            return jsonify({
                "success": False,
                "error": "Search query is required"
            }), 400

        max_results = data.get("max_results", 100)
        date_range_years = data.get("date_range_years", 5)
        include_abstracts_only = data.get("include_abstracts_only", True)
        api_key = data.get("api_key")

        db = get_db()
        try:
            # Check if connector exists
            connector = db.query(Connector).filter(
                Connector.tenant_id == g.tenant_id,
                Connector.connector_type == ConnectorType.PUBMED
            ).first()

            settings = {
                "search_query": search_query,
                "max_results": max_results,
                "date_range_years": date_range_years,
                "include_abstracts_only": include_abstracts_only
            }
            if api_key:
                settings["api_key"] = api_key

            is_first_connection = connector is None

            if connector:
                # Update existing
                connector.settings = settings
                connector.status = ConnectorStatus.CONNECTED
                connector.is_active = True
                connector.error_message = None
                connector.updated_at = utc_now()
            else:
                # Create new
                connector = Connector(
                    tenant_id=g.tenant_id,
                    user_id=g.user_id,
                    connector_type=ConnectorType.PUBMED,
                    name="PubMed",
                    status=ConnectorStatus.CONNECTED,
                    settings=settings
                )
                db.add(connector)

            db.commit()

            # Auto-sync on first connection
            if is_first_connection:
                connector_id = connector.id
                tenant_id = g.tenant_id
                user_id = g.user_id

                def run_initial_sync():
                    _run_connector_sync(
                        connector_id=connector_id,
                        connector_type="pubmed",
                        since=None,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        full_sync=True
                    )

                thread = threading.Thread(target=run_initial_sync)
                thread.daemon = True
                thread.start()

                print(f"[PubMed] Started auto-sync for first-time connection")

            return jsonify({
                "success": True,
                "message": "PubMed configured successfully",
                "connector_id": connector.id
            })

        finally:
            db.close()

    except Exception as e:
        print(f"[PubMed Configure] Error: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@integration_bp.route('/pubmed/status', methods=['GET'])
@require_auth
def pubmed_status():
    """Get PubMed connector status and configuration"""
    try:
        db = get_db()
        try:
            connector = db.query(Connector).filter(
                Connector.tenant_id == g.tenant_id,
                Connector.connector_type == ConnectorType.PUBMED,
                Connector.is_active == True
            ).first()

            if not connector:
                return jsonify({
                    "success": True,
                    "status": "not_configured",
                    "connector": None
                })

            return jsonify({
                "success": True,
                "status": connector.status.value,
                "connector": {
                    "id": connector.id,
                    "name": connector.name,
                    "status": connector.status.value,
                    "settings": connector.settings,
                    "last_sync_at": connector.last_sync_at.isoformat() if connector.last_sync_at else None,
                    "total_items_synced": connector.total_items_synced,
                    "error_message": connector.error_message
                }
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# QUARTZY INTEGRATION
# ============================================================================

@integration_bp.route('/quartzy/configure', methods=['POST'])
@require_auth
def quartzy_configure():
    """
    Configure Quartzy with an API access token.

    Request body:
    {
        "access_token": "your-quartzy-access-token"  // Required
    }
    """
    try:
        data = request.get_json()
        access_token = (data.get("access_token") or "").strip()

        if not access_token:
            return jsonify({
                "success": False,
                "error": "Access token is required. Generate one in Quartzy Settings > API."
            }), 400

        # Validate the token
        try:
            import requests as http_requests
            test_resp = http_requests.get(
                "https://api.quartzy.com/order-requests",
                headers={"Access-Token": access_token, "Accept": "application/json"},
                params={"page": 1},
                timeout=15
            )
            if test_resp.status_code == 401:
                return jsonify({
                    "success": False,
                    "error": "Invalid access token. Please check your Quartzy API token."
                }), 401
            if test_resp.status_code != 200:
                return jsonify({
                    "success": False,
                    "error": f"Quartzy API error: status {test_resp.status_code}"
                }), 400
        except Exception as api_err:
            return jsonify({
                "success": False,
                "error": f"Could not reach Quartzy API: {str(api_err)}"
            }), 400

        db = get_db()
        try:
            connector = db.query(Connector).filter(
                Connector.tenant_id == g.tenant_id,
                Connector.connector_type == ConnectorType.QUARTZY
            ).first()

            settings = {"max_items": 500, "include_order_requests": True}
            is_first_connection = connector is None

            if connector:
                connector.access_token = access_token
                connector.settings = settings
                connector.status = ConnectorStatus.CONNECTED
                connector.is_active = True
                connector.error_message = None
                connector.updated_at = utc_now()
            else:
                connector = Connector(
                    tenant_id=g.tenant_id,
                    user_id=g.user_id,
                    connector_type=ConnectorType.QUARTZY,
                    name="Quartzy",
                    status=ConnectorStatus.CONNECTED,
                    access_token=access_token,
                    settings=settings
                )
                db.add(connector)

            db.commit()

            # Auto-sync on first connection
            if is_first_connection:
                connector_id = connector.id
                tenant_id = g.tenant_id
                user_id = g.user_id

                def run_initial_sync():
                    _run_connector_sync(
                        connector_id=connector_id,
                        connector_type="quartzy",
                        since=None,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        full_sync=True
                    )

                thread = threading.Thread(target=run_initial_sync)
                thread.daemon = True
                thread.start()
                print(f"[Quartzy] Started auto-sync for first-time connection")

            return jsonify({
                "success": True,
                "message": "Quartzy connected successfully",
                "connector_id": connector.id
            })

        finally:
            db.close()

    except Exception as e:
        print(f"[Quartzy Configure] Error: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@integration_bp.route('/quartzy/upload-csv', methods=['POST'])
@require_auth
def quartzy_upload_csv():
    """
    Upload a Quartzy CSV or Excel export. Parses items, saves as documents, and embeds.

    Request: multipart/form-data with 'file' field (.csv or .xlsx)
    """
    try:
        if 'file' not in request.files:
            return jsonify({
                "success": False,
                "error": "No file provided. Please upload a CSV or Excel file."
            }), 400

        file = request.files['file']
        if not file.filename:
            return jsonify({
                "success": False,
                "error": "No file selected"
            }), 400

        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ('.csv', '.xlsx', '.xls'):
            return jsonify({
                "success": False,
                "error": "Unsupported file type. Please upload a .csv or .xlsx file."
            }), 400

        file_bytes = file.read()
        if not file_bytes:
            return jsonify({
                "success": False,
                "error": "File is empty"
            }), 400

        # Parse the CSV/Excel
        from connectors.quartzy_connector import QuartzyConnector
        connector_docs = QuartzyConnector.parse_csv(file_bytes, file.filename)

        if not connector_docs:
            return jsonify({
                "success": False,
                "error": "No items found in the file. Check that it has an 'Item Name' column."
            }), 400

        print(f"[Quartzy CSV] Parsed {len(connector_docs)} items from {file.filename}")

        # Save to database and embed
        db = get_db()
        try:
            tenant_id = g.tenant_id
            user_id = g.user_id
            saved_count = 0

            # Ensure connector record exists
            connector = db.query(Connector).filter(
                Connector.tenant_id == tenant_id,
                Connector.connector_type == ConnectorType.QUARTZY
            ).first()

            if not connector:
                connector = Connector(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    connector_type=ConnectorType.QUARTZY,
                    name="Quartzy",
                    status=ConnectorStatus.CONNECTED,
                    settings={"source": "csv_upload"}
                )
                db.add(connector)
                db.commit()

            for doc in connector_docs:
                # Check for duplicate
                existing = db.query(Document).filter(
                    Document.tenant_id == tenant_id,
                    Document.external_id == doc.doc_id
                ).first()

                if existing:
                    existing.content = doc.content
                    existing.title = doc.title
                    existing.doc_metadata = doc.metadata
                    existing.updated_at = utc_now()
                else:
                    db_doc = Document(
                        tenant_id=tenant_id,
                        connector_id=connector.id,
                        external_id=doc.doc_id,
                        source_type="quartzy_csv",
                        title=doc.title,
                        content=doc.content,
                        doc_metadata=doc.metadata,
                        classification=DocumentClassification.WORK,
                        classification_confidence=1.0,
                        status=DocumentStatus.CLASSIFIED,
                        source_created_at=utc_now()
                    )
                    db.add(db_doc)
                    saved_count += 1

            db.commit()

            # Update connector stats
            connector.total_items_synced = (connector.total_items_synced or 0) + saved_count
            connector.last_sync_at = utc_now()
            db.commit()

            # Embed in background
            def run_embedding():
                embed_db = get_db()
                try:
                    docs_to_embed = embed_db.query(Document).filter(
                        Document.tenant_id == tenant_id,
                        Document.source_type == "quartzy_csv",
                        Document.embedded_at == None
                    ).all()

                    if docs_to_embed:
                        embedding_service = get_embedding_service()
                        embed_result = embedding_service.embed_documents(
                            documents=docs_to_embed,
                            tenant_id=tenant_id,
                            db=embed_db,
                            force_reembed=False
                        )
                        print(f"[Quartzy CSV] Embedded {embed_result.get('embedded', 0)} documents")
                finally:
                    embed_db.close()

            thread = threading.Thread(target=run_embedding)
            thread.daemon = True
            thread.start()

            return jsonify({
                "success": True,
                "message": f"Imported {saved_count} items from {file.filename}",
                "documents_created": saved_count,
                "total_parsed": len(connector_docs)
            })

        finally:
            db.close()

    except Exception as e:
        print(f"[Quartzy CSV Upload] Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@integration_bp.route('/quartzy/status', methods=['GET'])
@require_auth
def quartzy_status():
    """Get Quartzy connector status"""
    try:
        db = get_db()
        try:
            connector = db.query(Connector).filter(
                Connector.tenant_id == g.tenant_id,
                Connector.connector_type == ConnectorType.QUARTZY,
                Connector.is_active == True
            ).first()

            if not connector:
                return jsonify({
                    "success": True,
                    "status": "not_configured",
                    "connector": None
                })

            return jsonify({
                "success": True,
                "status": connector.status.value,
                "connector": {
                    "id": connector.id,
                    "name": connector.name,
                    "status": connector.status.value,
                    "settings": connector.settings,
                    "last_sync_at": connector.last_sync_at.isoformat() if connector.last_sync_at else None,
                    "total_items_synced": connector.total_items_synced,
                    "error_message": connector.error_message
                }
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# WEBSITE SCRAPER INTEGRATION
# ============================================================================

@integration_bp.route('/webscraper/configure', methods=['POST'])
@require_auth
def webscraper_configure():
    """
    Configure website scraper.

    Request body:
    {
        "start_url": "https://example.com",  // Required
        "priority_paths": ["/resources/", "/protocols/"],  // Optional - paths to prioritize
        "max_depth": 2,  // Optional, default 2
        "max_pages": 20,  // Optional, default 20
        "include_pdfs": true,  // Optional, default true
        "wait_for_js": true,  // Optional, default true - render JavaScript
        "screenshot": true,  // Optional, default true - capture screenshots
        "crawl_delay": 1.0  // Optional, default 1.0 - seconds between requests
    }
    """
    try:
        data = request.get_json()
        start_url = data.get("start_url", "").strip()

        if not start_url:
            return jsonify({
                "success": False,
                "error": "start_url is required"
            }), 400

        # Validate URL format
        if not start_url.startswith(("http://", "https://")):
            start_url = "https://" + start_url

        # Validate URL is reachable (basic check)
        from urllib.parse import urlparse
        parsed = urlparse(start_url)
        if not parsed.netloc:
            return jsonify({
                "success": False,
                "error": "Invalid URL format"
            }), 400

        # Extract settings with defaults matching connector
        priority_paths = data.get("priority_paths", [])
        max_depth = min(max(int(data.get("max_depth", 5)), 1), 10)  # Clamp 1-10
        max_pages = min(max(int(data.get("max_pages", 50)), 1), 500)  # Clamp 1-500
        crawl_delay = float(data.get("crawl_delay", 0.3))

        db = get_db()
        try:
            # Check if connector exists
            connector = db.query(Connector).filter(
                Connector.tenant_id == g.tenant_id,
                Connector.connector_type == ConnectorType.WEBSCRAPER
            ).first()

            # Settings matching WebScraperConnector.OPTIONAL_SETTINGS
            settings = {
                "start_url": start_url,
                "priority_paths": priority_paths,
                "max_depth": max_depth,
                "max_pages": max_pages,
                "crawl_delay": crawl_delay,
                "timeout": 15,
                "exclude_patterns": [
                    "#", "mailto:", "tel:", "javascript:", "data:", "file:",
                    "login", "signin", "signup", "register", "logout", "logoff", "signout",
                    "/auth/", "/account/", "/user/", "/profile/", "/dashboard/", "/settings/",
                    "/admin/", "/password", "/forgot", "/reset", "/verify",
                    "cart", "checkout", "/basket", "/order", "/payment", "/billing",
                    "/search", "?search=", "?q=", "?query=", "?sort=", "?filter=",
                    "?utm_", "?fbclid=", "?gclid=", "?ref=", "?session",
                    "/api/", "/v1/", "/v2/", "/graphql", "/webhook",
                    "/test/", "/staging/", "/dev/", "/debug",
                ]
            }

            is_first_connection = connector is None

            if connector:
                # Update existing
                connector.settings = settings
                connector.status = ConnectorStatus.CONNECTED
                connector.is_active = True
                connector.error_message = None
                connector.updated_at = utc_now()
            else:
                # Create new
                from urllib.parse import urlparse
                parsed = urlparse(start_url)
                name = f"Web Scraper ({parsed.netloc})"

                connector = Connector(
                    tenant_id=g.tenant_id,
                    user_id=g.user_id,
                    connector_type=ConnectorType.WEBSCRAPER,
                    name=name,
                    status=ConnectorStatus.CONNECTED,
                    settings=settings
                )
                db.add(connector)

            db.commit()

            # Auto-sync on first connection
            if is_first_connection:
                connector_id = connector.id
                tenant_id = g.tenant_id
                user_id = g.user_id

                def run_initial_sync():
                    _run_connector_sync(
                        connector_id=connector_id,
                        connector_type="webscraper",
                        since=None,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        full_sync=True
                    )

                thread = threading.Thread(target=run_initial_sync)
                thread.daemon = True
                thread.start()

                print(f"[WebScraper] Started auto-sync for {start_url}")

            return jsonify({
                "success": True,
                "message": "Website scraper configured successfully",
                "connector_id": connector.id
            })

        finally:
            db.close()

    except Exception as e:
        print(f"[WebScraper Configure] Error: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@integration_bp.route('/webscraper/status', methods=['GET'])
@require_auth
def webscraper_status():
    """Get website scraper status and configuration"""
    try:
        db = get_db()
        try:
            connector = db.query(Connector).filter(
                Connector.tenant_id == g.tenant_id,
                Connector.connector_type == ConnectorType.WEBSCRAPER,
                Connector.is_active == True
            ).first()

            if not connector:
                return jsonify({
                    "success": True,
                    "status": "not_configured",
                    "connector": None
                })

            return jsonify({
                "success": True,
                "status": connector.status.value,
                "connector": {
                    "id": connector.id,
                    "name": connector.name,
                    "status": connector.status.value,
                    "settings": connector.settings,
                    "last_sync_at": connector.last_sync_at.isoformat() if connector.last_sync_at else None,
                    "total_items_synced": connector.total_items_synced,
                    "error_message": connector.error_message
                }
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# FIRECRAWL INTEGRATION (Full Website Crawler)
# ============================================================================

@integration_bp.route('/firecrawl/configure', methods=['POST'])
@require_auth
def firecrawl_configure():
    """
    Configure Firecrawl website crawler for comprehensive website crawling.

    Request body:
    {
        "start_url": "https://example.com",       // Required - base URL to crawl
        "max_pages": 100,                         // Optional, default 100 (max 500)
        "max_depth": 10,                          // Optional, default 10
        "include_subdomains": false,              // Optional - follow subdomains
        "include_external_links": false,          // Optional - follow external sites
        "include_patterns": [],                   // Optional - URL patterns to include
        "exclude_patterns": [],                   // Optional - URL patterns to exclude
    }

    Features:
    - Full recursive website crawling (not just BFS)
    - PDF extraction built-in
    - JavaScript rendering for SPAs
    - Automatic sitemap discovery
    - Clean markdown output
    """
    try:
        data = request.get_json()
        start_url = data.get("start_url", "").strip()

        if not start_url:
            return jsonify({
                "success": False,
                "error": "start_url is required"
            }), 400

        # Validate URL format
        if not start_url.startswith(("http://", "https://")):
            start_url = "https://" + start_url

        from urllib.parse import urlparse
        parsed = urlparse(start_url)
        if not parsed.netloc:
            return jsonify({
                "success": False,
                "error": "Invalid URL format"
            }), 400

        # Check if Firecrawl API key is configured
        firecrawl_key = os.getenv("FIRECRAWL_API_KEY", "")
        if not firecrawl_key:
            return jsonify({
                "success": False,
                "error": "Firecrawl API key not configured. Please add FIRECRAWL_API_KEY to your environment."
            }), 400

        # Extract settings with defaults
        max_pages = min(max(int(data.get("max_pages", 100)), 1), 500)
        max_depth = min(max(int(data.get("max_depth", 10)), 1), 20)
        include_subdomains = bool(data.get("include_subdomains", False))
        include_external = bool(data.get("include_external_links", False))
        include_patterns = data.get("include_patterns", [])
        exclude_patterns = data.get("exclude_patterns", [])

        # Default exclusions for common non-content paths
        default_exclusions = [
            "/login", "/signin", "/signup", "/register", "/logout",
            "/auth/*", "/account/*", "/admin/*", "/api/*",
            "/cart", "/checkout", "/payment",
        ]

        # Merge with user exclusions (filter out invalid patterns)
        valid_exclusions = [p for p in exclude_patterns if p and not p.startswith("?")]
        all_exclusions = list(set(valid_exclusions + default_exclusions))

        db = SessionLocal()
        try:
            # Check if connector exists
            connector = db.query(Connector).filter(
                Connector.tenant_id == g.tenant_id,
                Connector.connector_type == ConnectorType.FIRECRAWL
            ).first()

            settings = {
                "start_url": start_url,
                "max_pages": max_pages,
                "max_depth": max_depth,
                "include_subdomains": include_subdomains,
                "include_external_links": include_external,
                "include_patterns": include_patterns,
                "exclude_patterns": all_exclusions,
                "crawl_engine": "firecrawl",
            }

            is_first_connection = connector is None

            if connector:
                # Update existing
                connector.settings = settings
                connector.status = ConnectorStatus.CONNECTED
                connector.is_active = True
                connector.error_message = None
                connector.updated_at = utc_now()
            else:
                # Create new
                name = f"Firecrawl ({parsed.netloc})"
                connector = Connector(
                    tenant_id=g.tenant_id,
                    user_id=g.user_id,
                    connector_type=ConnectorType.FIRECRAWL,
                    name=name,
                    status=ConnectorStatus.CONNECTED,
                    settings=settings
                )
                db.add(connector)

            db.commit()

            # Auto-sync on first connection
            if is_first_connection:
                connector_id = connector.id
                tenant_id = g.tenant_id
                user_id = g.user_id

                def run_initial_sync():
                    _run_connector_sync(
                        connector_id=connector_id,
                        connector_type="firecrawl",
                        since=None,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        full_sync=True
                    )

                thread = threading.Thread(target=run_initial_sync)
                thread.daemon = True
                thread.start()

                print(f"[Firecrawl] Started auto-sync for {start_url}")

            return jsonify({
                "success": True,
                "message": "Firecrawl crawler configured successfully",
                "connector_id": connector.id,
                "settings": settings
            })

        finally:
            db.close()

    except Exception as e:
        print(f"[Firecrawl Configure] Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@integration_bp.route('/firecrawl/status', methods=['GET'])
@require_auth
def firecrawl_status():
    """Get Firecrawl crawler status and configuration"""
    try:
        db = SessionLocal()
        try:
            connector = db.query(Connector).filter(
                Connector.tenant_id == g.tenant_id,
                Connector.connector_type == ConnectorType.FIRECRAWL,
                Connector.is_active == True
            ).first()

            if not connector:
                return jsonify({
                    "success": True,
                    "status": "not_configured",
                    "connector": None,
                    "api_key_configured": bool(os.getenv("FIRECRAWL_API_KEY", ""))
                })

            return jsonify({
                "success": True,
                "status": connector.status.value,
                "connector": {
                    "id": connector.id,
                    "name": connector.name,
                    "status": connector.status.value,
                    "settings": connector.settings,
                    "last_sync_at": connector.last_sync_at.isoformat() if connector.last_sync_at else None,
                    "total_items_synced": connector.total_items_synced,
                    "error_message": connector.error_message
                },
                "api_key_configured": True
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@integration_bp.route('/firecrawl/map', methods=['POST'])
@require_auth
def firecrawl_map():
    """
    Get a quick sitemap of all URLs on a website without full crawl.
    Useful for previewing what pages will be crawled.
    """
    try:
        data = request.get_json()
        url = data.get("url", "").strip()

        if not url:
            return jsonify({
                "success": False,
                "error": "url is required"
            }), 400

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        from connectors.firecrawl_connector import FirecrawlScraper
        scraper = FirecrawlScraper()
        urls = scraper.map_website(url)

        return jsonify({
            "success": True,
            "url": url,
            "total_urls": len(urls),
            "urls": urls[:100]  # Return first 100 for preview
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# SYNC OPERATIONS
# ============================================================================

@integration_bp.route('/<connector_type>/sync', methods=['POST'])
@require_auth
def sync_connector(connector_type: str):
    """
    Trigger sync for a connector.

    URL params:
        connector_type: gmail, slack, or box

    Request body (optional):
    {
        "full_sync": false,  // If true, sync all data
        "since": "2024-01-01T00:00:00Z"  // Only sync after this date
    }

    Response:
    {
        "success": true,
        "job_id": "...",
        "message": "Sync started"
    }
    """
    try:
        # Map string to enum
        type_map = {
            "gmail": ConnectorType.GMAIL,
            "slack": ConnectorType.SLACK,
            "box": ConnectorType.BOX,
            "github": ConnectorType.GITHUB,
            "pubmed": ConnectorType.PUBMED,
            "webscraper": ConnectorType.WEBSCRAPER,
            "firecrawl": ConnectorType.FIRECRAWL,
            "notion": ConnectorType.NOTION,
            "gdrive": ConnectorType.GOOGLE_DRIVE,
            "gdocs": ConnectorType.GOOGLE_DOCS,
            "gsheets": ConnectorType.GOOGLE_SHEETS,
            "gslides": ConnectorType.GOOGLE_SLIDES,
            "gcalendar": ConnectorType.GOOGLE_CALENDAR,
            "zotero": ConnectorType.ZOTERO,
            "onedrive": ConnectorType.ONEDRIVE,
            "quartzy": ConnectorType.QUARTZY
        }

        if connector_type not in type_map:
            return jsonify({
                "success": False,
                "error": f"Invalid connector type: {connector_type}"
            }), 400

        data = request.get_json() or {}
        full_sync = data.get('full_sync', False)
        since_str = data.get('since')

        since = None
        if since_str and not full_sync:
            since = datetime.fromisoformat(since_str.replace('Z', '+00:00'))

        db = get_db()
        try:
            # Check for already-running sync (dedup)
            already_syncing = db.query(Connector).filter(
                Connector.tenant_id == g.tenant_id,
                Connector.connector_type == type_map[connector_type],
                Connector.status == ConnectorStatus.SYNCING
            ).first()

            if already_syncing:
                return jsonify({
                    "success": False,
                    "error": f"{connector_type.title()} sync already in progress",
                    "sync_id": (already_syncing.settings or {}).get('current_sync_id')
                }), 409

            # Retry logic for race condition after OAuth callback
            # (connector may not be visible immediately after creation)
            connector = None
            for attempt in range(3):
                connector = db.query(Connector).filter(
                    Connector.tenant_id == g.tenant_id,
                    Connector.connector_type == type_map[connector_type],
                    Connector.status == ConnectorStatus.CONNECTED
                ).first()
                if connector:
                    break
                if attempt < 2:
                    print(f"[Sync] Connector not found, retrying in 1s (attempt {attempt + 1}/3)...", flush=True)
                    time.sleep(1)
                    db.expire_all()  # Clear SQLAlchemy cache

            if not connector:
                return jsonify({
                    "success": False,
                    "error": f"{connector_type.title()} not connected"
                }), 400

            # Update status
            connector.status = ConnectorStatus.SYNCING
            db.commit()

            # Capture values BEFORE db closes (avoid SQLAlchemy lazy loading errors)
            conn_id = connector.id
            tenant = g.tenant_id
            user = g.user_id

        finally:
            db.close()

        # Start progress tracking
        from services.sync_progress_service import get_sync_progress_service
        progress_service = get_sync_progress_service()
        sync_id = progress_service.start_sync(tenant, user, connector_type)

        # Persist sync_id to connector settings (needed for email subscription DB lookup)
        try:
            db2 = get_db()
            c = db2.query(Connector).filter(Connector.id == conn_id).first()
            if c:
                s = c.settings or {}
                s['current_sync_id'] = sync_id
                s['sync_started_at'] = utc_now().isoformat()
                c.settings = s
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(c, 'settings')
                db2.commit()
            db2.close()
        except Exception as e:
            print(f"[Sync] Warning: Failed to persist sync_id to connector: {e}")

        # Submit sync to thread pool (bounded concurrency, prevents server OOM)
        _sync_executor.submit(
            _run_connector_sync,
            connector_id=conn_id,
            connector_type=connector_type,
            since=since,
            tenant_id=tenant,
            user_id=user,
            full_sync=full_sync,
            sync_id=sync_id
        )

        return jsonify({
            "success": True,
            "message": f"{connector_type.title()} sync started in background",
            "connector_id": conn_id,
            "sync_id": sync_id  # Return sync_id for progress tracking
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


def _sync_with_heartbeat(instance, since, sync_id, progress_service, connector_type, is_async=False):
    """Run sync with a heartbeat thread that sends progress updates during the blocking fetch phase"""
    import threading
    result = [None]
    error = [None]
    done = threading.Event()

    def heartbeat():
        tick = 0
        messages = [
            f'Connecting to {connector_type.replace("_", " ").title()}...',
            f'Fetching {connector_type.replace("_", " ").title()} data...',
            f'Downloading items from {connector_type.replace("_", " ").title()}...',
            f'Still fetching from {connector_type.replace("_", " ").title()}...',
        ]
        while not done.is_set():
            done.wait(timeout=5)
            if done.is_set():
                break
            tick += 1
            msg = messages[min(tick, len(messages) - 1)]
            if sync_id:
                try:
                    progress_service.update_progress(
                        sync_id, status='fetching',
                        stage=msg, overall_percent=0.0
                    )
                except Exception:
                    pass

    heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
    heartbeat_thread.start()

    try:
        if is_async:
            import asyncio
            loop = asyncio.new_event_loop()
            result[0] = loop.run_until_complete(instance.sync(since))
            loop.close()
        else:
            result[0] = instance.sync(since)
    except Exception as e:
        error[0] = e
    finally:
        done.set()
        heartbeat_thread.join(timeout=2)

    if error[0]:
        raise error[0]
    return result[0]


def _run_connector_sync(
    connector_id: str,
    connector_type: str,
    since: datetime,
    tenant_id: str,
    user_id: str,
    full_sync: bool = False,
    sync_id: str = None
):
    """Background sync function with progress tracking"""
    import time
    sync_start_time = time.time()
    print(f"[Sync] === _run_connector_sync START ===", flush=True)
    print(f"[Sync] connector_type={connector_type}, connector_id={connector_id}, sync_id={sync_id}, tenant_id={tenant_id}", flush=True)

    from services.sync_progress_service import get_sync_progress_service
    from services.email_notification_service import get_email_service

    # Get services
    progress_service = get_sync_progress_service()
    email_service = get_email_service()

    # Initialize progress (keep old dict for backward compatibility with frontend)
    progress_key = f"{tenant_id}:{connector_type}"
    sync_progress[progress_key] = {
        "status": "syncing",
        "progress": 5,
        "documents_found": 0,
        "documents_parsed": 0,
        "documents_embedded": 0,
        "current_file": None,
        "error": None,
        "started_at": utc_now().isoformat()
    }

    # Update new progress service
    if sync_id:
        progress_service.update_progress(sync_id, status='connecting', stage='Connecting to service...')

    # DB persistence helper for multi-worker polling support
    _last_db_persist_time = [0]
    def _persist_progress_to_db(db_session, connector_obj, status, stage, total_items=0, processed_items=0, failed_items=0, overall_percent=0, current_item=None, force=False):
        """Write current progress to Connector.settings['sync_progress'] in DB.
        Throttled to every 5s unless force=True (for phase transitions)."""
        now = time.time()
        if not force and (now - _last_db_persist_time[0]) < 5:
            return
        _last_db_persist_time[0] = now
        try:
            settings = dict(connector_obj.settings or {})
            settings['sync_progress'] = {
                'status': status, 'stage': stage, 'total_items': total_items,
                'processed_items': processed_items, 'failed_items': failed_items,
                'overall_percent': round(overall_percent, 1), 'current_item': current_item,
            }
            connector_obj.settings = settings
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(connector_obj, 'settings')
            db_session.commit()
        except Exception as persist_err:
            print(f"[Sync] Progress DB persist error (non-fatal): {persist_err}", flush=True)
            try: db_session.rollback()
            except Exception: pass

    db = get_db()
    try:
        connector = db.query(Connector).filter(
            Connector.id == connector_id
        ).first()

        print(f"[Sync] Connector found: {connector is not None}")

        if not connector:
            sync_progress[progress_key]["status"] = "error"
            sync_progress[progress_key]["error"] = "Connector not found"
            if sync_id:
                progress_service.complete_sync(sync_id, error_message="Connector not found in database")
            return

        print(f"[Sync] Connector settings: {connector.settings}")

        try:
            # Get connector class
            if connector_type == "gmail":
                from connectors.gmail_connector import GmailConnector
                ConnectorClass = GmailConnector
            elif connector_type == "slack":
                # Use basic SlackConnector (no filtering, captures all messages)
                from connectors.slack_connector import SlackConnector
                ConnectorClass = SlackConnector
            elif connector_type == "box":
                from connectors.box_connector import BoxConnector
                ConnectorClass = BoxConnector
            elif connector_type == "github":
                from connectors.github_connector import GitHubConnector
                ConnectorClass = GitHubConnector
            elif connector_type == "onedrive":
                from connectors.onedrive_connector import OneDriveConnector
                ConnectorClass = OneDriveConnector
            elif connector_type == "pubmed":
                from connectors.pubmed_connector import PubMedConnector
                ConnectorClass = PubMedConnector
            elif connector_type == "webscraper":
                print(f"[Sync] Importing WebScraperConnector...")
                from connectors.webscraper_connector import WebScraperConnector
                print(f"[Sync] WebScraperConnector imported successfully")
                ConnectorClass = WebScraperConnector
            elif connector_type == "firecrawl":
                print(f"[Sync] Importing FirecrawlConnector...")
                from connectors.firecrawl_connector import FirecrawlConnector
                print(f"[Sync] FirecrawlConnector imported successfully")
                ConnectorClass = FirecrawlConnector
            elif connector_type == "notion":
                print(f"[Sync] Importing NotionConnector...")
                from connectors.notion_connector import NotionConnector
                print(f"[Sync] NotionConnector imported successfully")
                ConnectorClass = NotionConnector
            elif connector_type == "gdrive":
                print(f"[Sync] Importing GDriveConnector...")
                from connectors.gdrive_connector import GDriveConnector
                print(f"[Sync] GDriveConnector imported successfully")
                ConnectorClass = GDriveConnector
            elif connector_type == "gdocs":
                print(f"[Sync] Importing GDocsConnector...")
                from connectors.gdocs_connector import GDocsConnector
                print(f"[Sync] GDocsConnector imported successfully")
                ConnectorClass = GDocsConnector
            elif connector_type == "gsheets":
                print(f"[Sync] Importing GSheetsConnector...")
                from connectors.gsheets_connector import GSheetsConnector
                print(f"[Sync] GSheetsConnector imported successfully")
                ConnectorClass = GSheetsConnector
            elif connector_type == "gslides":
                print(f"[Sync] Importing GSlidesConnector...")
                from connectors.gslides_connector import GSlidesConnector
                print(f"[Sync] GSlidesConnector imported successfully")
                ConnectorClass = GSlidesConnector
            elif connector_type == "gcalendar":
                print(f"[Sync] Importing GCalendarConnector...")
                from connectors.gcalendar_connector import GCalendarConnector
                print(f"[Sync] GCalendarConnector imported successfully")
                ConnectorClass = GCalendarConnector
            elif connector_type == "zotero":
                print(f"[Sync] Importing ZoteroConnector...")
                from connectors.zotero_connector import ZoteroConnector
                print(f"[Sync] ZoteroConnector imported successfully")
                ConnectorClass = ZoteroConnector
            elif connector_type == "quartzy":
                print(f"[Sync] Importing QuartzyConnector...")
                from connectors.quartzy_connector import QuartzyConnector
                print(f"[Sync] QuartzyConnector imported successfully")
                ConnectorClass = QuartzyConnector
            else:
                sync_progress[progress_key]["status"] = "error"
                sync_progress[progress_key]["error"] = f"Unknown connector type: {connector_type}"
                if sync_id:
                    progress_service.complete_sync(sync_id, error_message=f"Unknown connector type: {connector_type}")
                return

            # Create connector instance
            from connectors.base_connector import ConnectorConfig

            # Build credentials based on connector type
            if connector_type == "zotero":
                # Zotero uses api_key (stored as access_token) and zotero_user_id
                credentials = {
                    "api_key": connector.access_token,
                    "user_id": connector.settings.get("zotero_user_id") if connector.settings else None
                }
            elif connector_type == "quartzy":
                # Quartzy uses access_token header auth
                credentials = {
                    "access_token": connector.access_token
                }
            else:
                # Standard OAuth credentials
                credentials = {
                    "access_token": connector.access_token,
                    "refresh_token": connector.refresh_token
                }

            config = ConnectorConfig(
                connector_type=connector_type,
                user_id=user_id,
                credentials=credentials,
                settings=connector.settings or {}
            )

            instance = ConnectorClass(config)

            # Update progress - connecting
            sync_progress[progress_key]["progress"] = 10
            sync_progress[progress_key]["current_file"] = "Connecting to service..."
            if sync_id:
                progress_service.update_progress(sync_id, status='connecting', stage=f'Connecting to {connector_type.title()}...')

            # Run sync
            # Note: Only async connectors (gmail, box, github, onedrive) need an event loop
            # Sync connectors (slack, webscraper, notion, gdrive) run directly without asyncio
            import asyncio
            loop = None  # Only created for async connectors

            # List of synchronous connectors that don't need event loop
            # Note: firecrawl uses `async def sync()` but internally uses synchronous requests library
            sync_connectors = {'slack', 'webscraper', 'notion', 'gdrive', 'gdocs', 'gsheets', 'gslides', 'gcalendar', 'firecrawl', 'onedrive'}

            if connector_type not in sync_connectors:
                print(f"[Sync] Creating event loop for async connector: {connector_type}")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                print(f"[Sync] Event loop ready, starting sync...")
            else:
                print(f"[Sync] Synchronous connector: {connector_type}, no event loop needed")

            try:
                # Check if this is the first sync (no documents exist for this connector)
                existing_doc_count = db.query(Document).filter(
                    Document.tenant_id == tenant_id,
                    Document.connector_id == connector.id
                ).count()

                # Force full sync if no EMBEDDED documents exist yet (first successful sync)
                embedded_doc_count = db.query(Document).filter(
                    Document.tenant_id == tenant_id,
                    Document.connector_id == connector.id,
                    Document.embedded_at.isnot(None)
                ).count()

                if embedded_doc_count == 0:
                    full_sync = True
                    since = None
                    print(f"[Sync] First sync detected for {connector_type} (no embedded docs), doing full sync")

                    # Clear any deleted document records on first sync (fresh start)
                    deleted_count = db.query(DeletedDocument).filter(
                        DeletedDocument.tenant_id == tenant_id,
                        DeletedDocument.connector_id == connector.id
                    ).delete()
                    if deleted_count > 0:
                        db.commit()
                        print(f"[Sync] Cleared {deleted_count} deleted document records for fresh start")
                # Use last sync time if not doing full sync
                elif not since and connector.last_sync_at and not full_sync:
                    since = connector.last_sync_at

                # Update progress - fetching (indeterminate phase, no percentage)
                sync_progress[progress_key]["progress"] = 0
                sync_progress[progress_key]["status"] = "fetching"
                sync_progress[progress_key]["current_file"] = "Fetching documents..."
                if sync_id:
                    progress_service.update_progress(
                        sync_id, status='fetching',
                        stage=f'Fetching {connector_type.title()} data...',
                        overall_percent=0.0
                    )

                # For webscraper, set initial total_items to max_pages to avoid 100% progress at start
                if connector_type == 'webscraper':
                    max_pages = instance.config.settings.get('max_pages', 50)
                    if sync_id:
                        progress_service.update_progress(
                            sync_id,
                            status='syncing',
                            stage='Crawling website...',
                            total_items=max_pages
                        )
                    # WebScraper uses synchronous requests + BeautifulSoup - call directly without event loop
                    print(f"[Sync] Calling webscraper sync directly (synchronous)")
                    documents = instance._sync_sync(since)
                elif connector_type == 'slack':
                    # Slack uses synchronous WebClient - call directly without event loop
                    # This avoids "Cannot run the event loop while another loop is running" error with gevent
                    if sync_id:
                        progress_service.update_progress(sync_id, status='syncing', stage='Fetching Slack messages...')
                    print(f"[Sync] Calling slack sync directly (synchronous)")
                    documents = instance._sync_sync(since)
                elif connector_type == 'notion':
                    # Notion uses synchronous notion-client SDK
                    if sync_id:
                        progress_service.update_progress(sync_id, status='syncing', stage='Fetching Notion pages...')
                    print(f"[Sync] Calling notion sync with heartbeat (synchronous)")
                    documents = _sync_with_heartbeat(instance, since, sync_id, progress_service, connector_type)
                    print(f"[Sync] Notion sync returned {len(documents) if documents else 0} documents")
                elif connector_type == 'gdrive':
                    # GDrive uses synchronous Google API
                    if sync_id:
                        progress_service.update_progress(sync_id, status='syncing', stage='Fetching Google Drive files...')
                    print(f"[Sync] Calling gdrive sync with heartbeat (synchronous)")
                    documents = _sync_with_heartbeat(instance, since, sync_id, progress_service, connector_type)
                    print(f"[Sync] GDrive sync returned {len(documents) if documents else 0} documents")
                elif connector_type == 'firecrawl':
                    # Firecrawl uses synchronous requests library - call directly
                    max_pages = instance.config.settings.get('max_pages', 100)
                    if sync_id:
                        progress_service.update_progress(
                            sync_id,
                            status='syncing',
                            stage='Crawling website with Firecrawl...',
                            total_items=max_pages
                        )
                    print(f"[Sync] Calling firecrawl sync directly (synchronous)", flush=True)
                    documents = instance.sync(since)
                    print(f"[Sync] Firecrawl sync returned {len(documents) if documents else 0} documents", flush=True)
                elif connector_type == 'gdocs':
                    if sync_id:
                        progress_service.update_progress(sync_id, status='syncing', stage='Fetching Google Docs...')
                    print(f"[Sync] Calling gdocs sync with heartbeat (synchronous)")
                    documents = _sync_with_heartbeat(instance, since, sync_id, progress_service, connector_type)
                    print(f"[Sync] GDocs sync returned {len(documents) if documents else 0} documents")
                elif connector_type == 'gsheets':
                    if sync_id:
                        progress_service.update_progress(sync_id, status='syncing', stage='Fetching Google Sheets...')
                    print(f"[Sync] Calling gsheets sync with heartbeat (synchronous)")
                    documents = _sync_with_heartbeat(instance, since, sync_id, progress_service, connector_type)
                    print(f"[Sync] GSheets sync returned {len(documents) if documents else 0} documents")
                elif connector_type == 'gslides':
                    if sync_id:
                        progress_service.update_progress(sync_id, status='syncing', stage='Fetching Google Slides...')
                    print(f"[Sync] Calling gslides sync with heartbeat (synchronous)")
                    documents = _sync_with_heartbeat(instance, since, sync_id, progress_service, connector_type)
                    print(f"[Sync] GSlides sync returned {len(documents) if documents else 0} documents")
                elif connector_type == 'gcalendar':
                    if sync_id:
                        progress_service.update_progress(sync_id, status='syncing', stage='Fetching Google Calendar events...')
                    print(f"[Sync] Calling gcalendar sync with heartbeat (synchronous)")
                    documents = _sync_with_heartbeat(instance, since, sync_id, progress_service, connector_type)
                    print(f"[Sync] GCalendar sync returned {len(documents) if documents else 0} documents")
                elif connector_type == 'onedrive':
                    # OneDrive uses synchronous requests library
                    if sync_id:
                        progress_service.update_progress(sync_id, status='syncing', stage='Fetching OneDrive files...')
                    print(f"[Sync] Calling onedrive sync with heartbeat (synchronous)", flush=True)
                    documents = _sync_with_heartbeat(instance, since, sync_id, progress_service, connector_type)
                    print(f"[Sync] OneDrive sync returned {len(documents) if documents else 0} documents", flush=True)
                elif connector_type == 'github':
                    # GitHub sync does LLM analysis which takes time - update progress at each stage
                    if sync_id:
                        progress_service.update_progress(sync_id, status='syncing', stage='Connecting to GitHub...')
                    print(f"[Sync] Starting GitHub sync with LLM analysis...")

                    # Run sync (which includes fetching code and LLM analysis)
                    if sync_id:
                        progress_service.update_progress(sync_id, status='syncing', stage='Fetching repository code...', total_items=1)
                    documents = loop.run_until_complete(instance.sync(since))

                    if sync_id:
                        progress_service.update_progress(
                            sync_id,
                            status='parsing',
                            stage='Code analysis complete, processing documents...',
                            processed_items=len(documents) if documents else 0,
                            total_items=len(documents) if documents else 1
                        )
                    print(f"[Sync] GitHub sync returned {len(documents) if documents else 0} documents")
                elif connector_type == 'zotero':
                    # Zotero uses async methods - needs event loop with heartbeat
                    if sync_id:
                        progress_service.update_progress(sync_id, status='syncing', stage='Fetching Zotero library...')
                    print(f"[Sync] Starting Zotero sync with heartbeat...")
                    documents = _sync_with_heartbeat(instance, since, sync_id, progress_service, connector_type, is_async=True)
                    if sync_id and documents:
                        progress_service.update_progress(
                            sync_id,
                            status='parsing',
                            stage=f'Processing {len(documents)} research papers...',
                            processed_items=0,
                            total_items=len(documents)
                        )
                    print(f"[Sync] Zotero sync returned {len(documents) if documents else 0} documents")
                elif sync_id:
                    progress_service.update_progress(sync_id, status='syncing', stage='Fetching documents...')
                    documents = loop.run_until_complete(instance.sync(since))
                else:
                    documents = loop.run_until_complete(instance.sync(since))

                # Note: total_items is set AFTER deduplication below for accurate progress

                # CRITICAL: Refresh database session after long-running sync
                # The sync can take 3+ minutes for large connectors (GDrive with 147 files)
                # During this time, the PostgreSQL connection times out (SSL SYSCALL error: EOF)
                # We need to close the stale session and create a fresh one
                connector_id_for_refresh = connector.id  # Save connector ID before closing session
                elapsed = time.time() - sync_start_time
                print(f"[Sync] Refreshing database session after sync (elapsed: {elapsed:.1f}s)...", flush=True)
                try:
                    db.close()
                except Exception as e:
                    print(f"[Sync] Warning: Error closing old session: {e}")

                db = get_db()  # Get fresh database session
                connector = db.query(Connector).filter(Connector.id == connector_id_for_refresh).first()
                if not connector:
                    raise Exception(f"Failed to re-fetch connector after session refresh")
                print(f"[Sync] Database session refreshed successfully")

                # Get list of deleted external_ids to skip (user permanently deleted these)
                deleted_external_ids = set(
                    d.external_id for d in db.query(DeletedDocument.external_id).filter(
                        DeletedDocument.tenant_id == tenant_id,
                        DeletedDocument.connector_id == connector.id
                    ).all()
                )
                print(f"[Sync] Deleted document IDs: {len(deleted_external_ids)}")

                # Get list of existing external_ids to avoid duplicates
                # CRITICAL: Only skip documents that:
                # 1. Are fully embedded (embedded_at != None)
                # 2. AND have actual content (to allow re-processing of empty content docs)
                existing_docs_query = db.query(Document).filter(
                    Document.tenant_id == tenant_id,
                    Document.connector_id == connector.id,
                    Document.external_id != None,
                    Document.embedded_at != None  # Only skip if already embedded
                ).all()

                # Additionally filter out docs with empty/minimal content (likely failed extractions)
                existing_external_ids = set(
                    doc.external_id for doc in existing_docs_query
                    if doc.content and len(doc.content.strip()) > 100  # Must have real content
                )
                print(f"[Sync] Existing embedded document IDs with content: {len(existing_external_ids)}")

                # Check un-embedded existing documents for debugging
                un_embedded_existing = db.query(Document).filter(
                    Document.tenant_id == tenant_id,
                    Document.connector_id == connector.id,
                    Document.external_id != None,
                    Document.embedded_at == None  # Not embedded
                ).all()
                un_embedded_ids = [doc.external_id for doc in un_embedded_existing]
                print(f"[Sync] Un-embedded existing documents: {len(un_embedded_existing)} - {un_embedded_ids[:5]}")

                # Delete documents with empty content so they can be re-synced
                empty_content_docs = [doc for doc in un_embedded_existing if not doc.content or len(doc.content.strip()) < 100]
                if empty_content_docs:
                    print(f"[Sync] Deleting {len(empty_content_docs)} documents with empty content for re-sync")
                    for doc in empty_content_docs:
                        db.delete(doc)
                    db.commit()

                # Filter out deleted and existing documents
                original_count = len(documents) if documents else 0
                documents = [
                    doc for doc in (documents or [])
                    if doc.doc_id not in deleted_external_ids and doc.doc_id not in existing_external_ids
                ]
                skipped_deleted = original_count - len(documents) - len([
                    d for d in (documents or []) if d.doc_id in existing_external_ids
                ])

                # Update progress - documents found (AFTER dedup for accurate total)
                new_doc_count = len(documents) if documents else 0
                sync_progress[progress_key]["documents_found"] = new_doc_count
                sync_progress[progress_key]["documents_skipped"] = original_count - new_doc_count
                sync_progress[progress_key]["progress"] = 0
                sync_progress[progress_key]["status"] = "saving"
                if sync_id:
                    progress_service.update_progress(
                        sync_id,
                        status='saving',
                        stage=f'Saving {new_doc_count} new documents...',
                        total_items=new_doc_count,
                        processed_items=0,
                        overall_percent=0.0
                    )
                    _persist_progress_to_db(db, connector, 'saving', f'Saving {new_doc_count} new documents...', total_items=new_doc_count, force=True)

                print(f"[Sync] Found {original_count} docs, skipping {original_count - len(documents)} (deleted or existing), processing {len(documents)}")

                # Handle case where sync returned 0 documents and connector has error
                # Check if the connector instance reported an error during sync
                connector_error = getattr(instance, 'last_error', None)
                if not documents and original_count == 0 and connector_error:
                    print(f"[Sync] ERROR: Connector reported error with 0 docs: {connector_error}", flush=True)
                    raise Exception(connector_error)
                elif not documents and original_count == 0 and connector_type in ('webscraper', 'firecrawl'):
                    error_msg = "Website returned no content. The site may be blocking cloud servers, or the pages may have no extractable text."
                    print(f"[Sync] ERROR: {error_msg}", flush=True)
                    raise Exception(error_msg)

                # Handle case where all documents already exist
                if not documents and original_count > 0:
                    print(f"[Sync] All {original_count} documents already exist and are embedded. Skipping sync.")
                    if sync_id:
                        progress_service.update_progress(
                            sync_id,
                            status='complete',
                            stage=f'All {original_count} documents already synced. No new content to process.',
                            total_items=original_count,
                            processed_items=original_count
                        )
                        progress_service.complete_sync(sync_id)

                    sync_progress[progress_key]["status"] = "completed"
                    sync_progress[progress_key]["progress"] = 100
                    sync_progress[progress_key]["message"] = f"All {original_count} documents already synced"
                    # Note: save_sync_state was removed - state is managed via progress_service

                    # Update connector status to CONNECTED (important for background thread)
                    connector.status = ConnectorStatus.CONNECTED
                    connector.last_sync_status = "success"
                    db.commit()
                    print(f"[Sync] All {original_count} documents already synced, no new content", flush=True)
                    return  # Exit background thread cleanly (not jsonify - we're in a background thread)

                # Save documents to database with progress updates
                # Commit in small batches to avoid database connection timeouts
                # Render PostgreSQL drops connections after ~30s idle or on long transactions
                BATCH_SIZE = 10  # Smaller batches = more frequent commits = less risk of SSL timeout
                total_docs = len(documents) if documents else 1
                docs_in_batch = 0
                total_committed = 0

                def _safe_commit(db_session, batch_desc="batch"):
                    """Commit with error recovery for connection drops.
                    On failure: rollback, wait for DB recovery, refresh session, and continue.
                    Lost docs will be picked up on next sync (they won't exist in DB).
                    """
                    try:
                        db_session.commit()
                        return db_session  # Success, return same session
                    except Exception as commit_err:
                        err_name = type(commit_err).__name__
                        print(f"[Sync] ERROR committing {batch_desc}: {err_name}: {commit_err}", flush=True)

                        # Rollback failed transaction
                        try:
                            db_session.rollback()
                            print(f"[Sync] Rolled back failed transaction", flush=True)
                        except Exception:
                            pass

                        # Close old session
                        try:
                            db_session.close()
                        except Exception:
                            pass

                        # Retry with exponential backoff (DB may be in recovery mode)
                        max_retries = 4
                        for attempt in range(max_retries):
                            wait_secs = 2 ** attempt  # 1, 2, 4, 8 seconds
                            print(f"[Sync] Waiting {wait_secs}s before reconnect attempt {attempt + 1}/{max_retries}...", flush=True)
                            time.sleep(wait_secs)

                            try:
                                db_session = get_db()
                                # Verify connection works
                                nonlocal connector
                                connector = db_session.query(Connector).filter(Connector.id == connector_id_for_refresh).first()
                                if connector:
                                    print(f"[Sync] DB reconnected on attempt {attempt + 1} (batch docs lost, will retry on next sync)", flush=True)
                                    return db_session
                                else:
                                    print(f"[Sync] Reconnected but connector not found, retrying...", flush=True)
                                    db_session.close()
                            except Exception as retry_err:
                                print(f"[Sync] Reconnect attempt {attempt + 1} failed: {type(retry_err).__name__}: {retry_err}", flush=True)
                                try:
                                    db_session.close()
                                except Exception:
                                    pass

                        # All retries exhausted
                        raise Exception(f"DB unavailable after {max_retries} retries (last error: {err_name}: {commit_err})")

                for i, doc in enumerate(documents):
                    # Phase 1 (Save): 0% - 33%
                    save_pct = ((i + 1) / total_docs) * 33.0
                    sync_progress[progress_key]["progress"] = int(save_pct)
                    sync_progress[progress_key]["documents_parsed"] = i + 1
                    current_doc_name = doc.title[:50] if doc.title else f"Document {i+1}"
                    sync_progress[progress_key]["current_file"] = current_doc_name

                    # Update progress service with accurate percent
                    if sync_id:
                        progress_service.increment_processed(
                            sync_id,
                            current_item=current_doc_name,
                            overall_percent=save_pct
                        )

                    # Map connector Document attributes to database Document fields
                    # Connector Document uses: doc_id, source, content, title, metadata, timestamp, author
                    # Database Document expects: external_id, source_type, content, title, metadata, source_created_at, etc.

                    # Auto-classify research sources as WORK (they're academic papers, not personal)
                    research_sources = {'pubmed', 'webscraper', 'quartzy', 'quartzy_csv'}
                    is_research = (
                        doc.source.lower() in research_sources or
                        getattr(doc, 'doc_type', None) == 'research_paper'
                    )

                    if is_research:
                        # Research papers are always WORK
                        classification = DocumentClassification.WORK
                        status = DocumentStatus.CONFIRMED
                        classification_confidence = 1.0
                        classification_reason = f"Auto-classified as WORK: {doc.source} research content"
                        print(f"[Sync] Auto-classified research document as WORK: {doc.title[:50]}")
                    elif doc.source in ('onedrive', 'gdrive', 'box', 'notion', 'github'):
                        # Cloud storage and known work sources auto-confirm as WORK
                        classification = DocumentClassification.WORK
                        status = DocumentStatus.CONFIRMED
                        classification_confidence = 0.9
                        classification_reason = f"Auto-confirmed as WORK: {doc.source} document"
                    else:
                        # Other sources need AI classification
                        classification = DocumentClassification.UNKNOWN
                        status = DocumentStatus.PENDING
                        classification_confidence = None
                        classification_reason = None

                    # DEBUG: Log Slack metadata being saved
                    if doc.source == 'slack' and doc.metadata:
                        print(f"[Sync] DEBUG Slack doc metadata: team_domain={doc.metadata.get('team_domain')}, channel_id={doc.metadata.get('channel_id')}, message_ts={doc.metadata.get('message_ts')}", flush=True)

                    db_doc = Document(
                        tenant_id=tenant_id,
                        connector_id=connector.id,
                        external_id=doc.doc_id,
                        source_type=doc.source,
                        title=doc.title,
                        content=doc.content,
                        doc_metadata=doc.metadata,  # Fixed: field is doc_metadata not metadata
                        sender=doc.author,
                        source_url=doc.url,  # Added: preserve source URL
                        source_created_at=doc.timestamp,
                        source_updated_at=doc.timestamp,
                        status=status,
                        classification=classification,
                        classification_confidence=classification_confidence,
                        classification_reason=classification_reason
                    )
                    db.add(db_doc)
                    docs_in_batch += 1

                    # Commit in batches to avoid DB connection timeouts
                    if docs_in_batch >= BATCH_SIZE:
                        db = _safe_commit(db, batch_desc=f"batch {total_committed+1}-{total_committed+docs_in_batch}/{total_docs}")
                        total_committed += docs_in_batch
                        print(f"[Sync] Committed batch of {docs_in_batch} documents ({total_committed}/{total_docs})", flush=True)
                        docs_in_batch = 0

                # Commit any remaining documents
                if docs_in_batch > 0:
                    db = _safe_commit(db, batch_desc=f"final batch {total_committed+1}-{total_committed+docs_in_batch}/{total_docs}")
                    total_committed += docs_in_batch
                    print(f"[Sync] Committed final batch of {docs_in_batch} documents ({total_committed} total)", flush=True)

                # === PHASE 2: EXTRACTION (33% - 66%) ===
                elapsed = time.time() - sync_start_time
                print(f"[Sync] All {total_committed} documents committed to DB (elapsed: {elapsed:.1f}s), starting extraction phase...", flush=True)
                sync_progress[progress_key]["status"] = "extracting"
                sync_progress[progress_key]["progress"] = 33
                sync_progress[progress_key]["current_file"] = "Extracting document summaries..."
                if sync_id:
                    progress_service.update_progress(
                        sync_id, status='extracting',
                        stage='Extracting document summaries...',
                        overall_percent=33.0
                    )
                    _persist_progress_to_db(db, connector, 'extracting', 'Extracting document summaries...', total_items=total_committed, processed_items=total_committed, overall_percent=33.0, force=True)

                try:
                    # Query un-embedded documents for this connector (including from previous failed syncs)
                    # IMPORTANT: Skip PENDING/UNKNOWN docs (Gmail/Slack) — they need user review before embedding
                    un_embedded_docs = db.query(Document).filter(
                        Document.tenant_id == tenant_id,
                        Document.connector_id == connector.id,
                        Document.embedded_at == None,
                        Document.status != DocumentStatus.PENDING
                    ).all()

                    doc_ids = [doc.id for doc in un_embedded_docs]
                    print(f"[Sync] Found {len(doc_ids)} total un-embedded documents (including from previous syncs)")

                    if doc_ids:
                        docs_to_embed = db.query(Document).filter(
                            Document.id.in_(doc_ids),
                            Document.tenant_id == tenant_id
                        ).all()

                        embed_total = len(docs_to_embed)

                        # STEP 1: Extract structured summaries (33% - 66%)
                        def extraction_progress(cur, total, msg):
                            pct = 33.0 + (cur / total) * 33.0
                            sync_progress[progress_key]["progress"] = int(pct)
                            sync_progress[progress_key]["current_file"] = msg
                            if sync_id:
                                progress_service.update_progress(
                                    sync_id,
                                    current_item=msg,
                                    overall_percent=pct,
                                    stage=f'Extracting summaries ({cur}/{total})...'
                                )

                        try:
                            extraction_service = get_extraction_service()
                            extract_result = extraction_service.extract_documents(
                                documents=docs_to_embed,
                                db=db,
                                force=False,
                                progress_callback=extraction_progress
                            )
                            sync_progress[progress_key]["documents_extracted"] = extract_result.get('extracted', 0)
                            print(f"[Sync] Extracted summaries for {extract_result.get('extracted', 0)} documents", flush=True)
                        except Exception as extract_error:
                            print(f"[Sync] EXTRACTION ERROR: {type(extract_error).__name__}: {extract_error}", flush=True)
                            import traceback
                            traceback.print_exc()
                            sync_progress[progress_key]["extraction_error"] = str(extract_error)

                        # === PHASE 3: EMBEDDING (66% - 99%) ===
                        sync_progress[progress_key]["status"] = "embedding"
                        sync_progress[progress_key]["progress"] = 66
                        sync_progress[progress_key]["current_file"] = "Embedding documents..."
                        if sync_id:
                            progress_service.update_progress(
                                sync_id, status='embedding',
                                stage='Embedding documents...',
                                overall_percent=66.0
                            )
                            _persist_progress_to_db(db, connector, 'embedding', 'Embedding documents...', overall_percent=66.0, force=True)

                        def embedding_progress(cur, total, msg):
                            pct = 66.0 + (cur / total) * 33.0
                            sync_progress[progress_key]["progress"] = int(pct)
                            sync_progress[progress_key]["current_file"] = msg
                            if sync_id:
                                progress_service.update_progress(
                                    sync_id,
                                    current_item=msg,
                                    overall_percent=pct,
                                    stage=f'Embedding documents ({cur}/{total})...'
                                )

                        print(f"[Sync] Calling embedding_service.embed_documents() with {embed_total} documents", flush=True)
                        embedding_service = get_embedding_service()
                        embed_result = embedding_service.embed_documents(
                            documents=docs_to_embed,
                            tenant_id=tenant_id,
                            db=db,
                            force_reembed=False,
                            progress_callback=embedding_progress
                        )

                        sync_progress[progress_key]["documents_embedded"] = embed_result.get('embedded', 0)
                        sync_progress[progress_key]["chunks_created"] = embed_result.get('chunks', 0)

                        print(f"[Sync] Embedding result: embedded={embed_result.get('embedded', 0)}, chunks={embed_result.get('chunks', 0)}, skipped={embed_result.get('skipped', 0)}", flush=True)
                        if embed_result.get('errors'):
                            print(f"[Sync] Embedding errors: {embed_result['errors']}", flush=True)
                    else:
                        print(f"[Sync] No un-embedded documents found - all already processed")
                        # Skip extraction/embedding phases entirely
                        if sync_id:
                            progress_service.update_progress(sync_id, overall_percent=99.0)

                except Exception as embed_error:
                    print(f"[Sync] EXTRACTION/EMBEDDING ERROR: {type(embed_error).__name__}: {embed_error}", flush=True)
                    import traceback
                    traceback.print_exc()
                    sync_progress[progress_key]["embedding_error"] = str(embed_error)
                    # Surface embedding errors to user via progress service
                    if sync_id:
                        progress_service.update_progress(
                            sync_id,
                            status='embedding_error',
                            stage=f'Documents saved but embedding failed: {str(embed_error)[:200]}',
                        )

                sync_progress[progress_key]["progress"] = 99

                # Refresh session before final connector update (embedding can take minutes)
                try:
                    db.close()
                except Exception:
                    pass
                db = get_db()
                connector = db.query(Connector).filter(Connector.id == connector_id_for_refresh).first()
                if not connector:
                    raise Exception("Failed to re-fetch connector for final status update")

                # Update connector
                connector.status = ConnectorStatus.CONNECTED
                connector.last_sync_at = utc_now()
                connector.last_sync_status = "success"
                connector.last_sync_items_count = len(documents)
                connector.total_items_synced += len(documents)
                connector.error_message = None

                db = _safe_commit(db, batch_desc="final connector status update")

                # Mark complete
                elapsed = time.time() - sync_start_time
                print(f"[Sync] === SYNC COMPLETE === connector_type={connector_type}, documents={len(documents)}, elapsed={elapsed:.1f}s", flush=True)
                sync_progress[progress_key]["status"] = "completed"
                sync_progress[progress_key]["progress"] = 100
                sync_progress[progress_key]["current_file"] = None
                sync_progress[progress_key]["overall_percent"] = 100

                # Complete progress tracking
                if sync_id:
                    progress_service.complete_sync(sync_id)
                    _persist_progress_to_db(db, connector, 'complete', 'Sync complete', overall_percent=100.0, force=True)

            finally:
                # Only close the event loop if we created one (async connectors only)
                if loop is not None:
                    loop.close()

        except Exception as e:
            # Log the full error with traceback for debugging
            import traceback
            error_msg = str(e)
            err_type = type(e).__name__
            print(f"[Sync] FATAL ERROR during {connector_type} sync: {err_type}: {error_msg}", flush=True)
            traceback.print_exc()

            # Rollback any pending transaction before attempting error status update
            # Without this, PendingRollbackError will cascade from the original failure
            try:
                db.rollback()
                print(f"[Sync] Rolled back failed transaction", flush=True)
            except Exception as rollback_err:
                print(f"[Sync] Rollback failed: {rollback_err}, creating fresh session", flush=True)
                try:
                    db.close()
                except Exception:
                    pass
                db = get_db()

            # Try to update connector error status in the database
            try:
                connector = db.query(Connector).filter(Connector.id == connector_id).first()
                if connector:
                    connector.status = ConnectorStatus.ERROR
                    connector.last_sync_status = "error"
                    connector.last_sync_error = error_msg[:500]  # Truncate to avoid DB field overflow
                    connector.error_message = error_msg[:500]
                    db.commit()
                    print(f"[Sync] Updated connector error status in database", flush=True)
                else:
                    print(f"[Sync] WARNING: Could not find connector {connector_id} to update error status", flush=True)
            except Exception as status_err:
                print(f"[Sync] ERROR: Failed to update connector error status: {type(status_err).__name__}: {status_err}", flush=True)

            # Mark failed in progress service
            if sync_id:
                try:
                    progress_service.complete_sync(sync_id, error_message=error_msg)
                except Exception as progress_err:
                    print(f"[Sync] ERROR: Failed to update progress service: {progress_err}", flush=True)

            # Update in-memory progress with error
            sync_progress[progress_key]["status"] = "error"
            sync_progress[progress_key]["error"] = error_msg[:500]

    finally:
        try:
            db.close()
        except Exception:
            pass


@integration_bp.route('/sync/cancel-all', methods=['POST'])
@require_auth
def cancel_all_syncs():
    """
    EMERGENCY: Cancel ALL ongoing syncs for current tenant.
    Also resets any SYNCING connectors in the database.

    Response:
    {
        "success": true,
        "message": "All syncs cancelled",
        "cancelled": ["webscraper", "firecrawl", "slack"]
    }
    """
    try:
        tenant_id = g.tenant_id
        cancelled = []

        # Find and cancel all in-memory syncs for this tenant
        keys_to_cancel = [key for key in sync_progress.keys() if key.startswith(f"{tenant_id}:")]

        for key in keys_to_cancel:
            connector_type = key.split(":", 1)[1]
            sync_progress[key] = {
                "status": "cancelled",
                "progress": 0,
                "documents_found": 0,
                "documents_parsed": 0,
                "documents_embedded": 0,
                "current_file": None,
                "error": "Sync cancelled by user (emergency stop)"
            }
            cancelled.append(connector_type)

        # CRITICAL: Also reset ALL SYNCING connectors in the database
        db = None
        try:
            db = get_db()
            syncing_connectors = db.query(Connector).filter(
                Connector.tenant_id == tenant_id,
                Connector.status == ConnectorStatus.SYNCING
            ).all()

            for connector in syncing_connectors:
                connector.status = ConnectorStatus.CONNECTED
                connector.error_message = "Sync cancelled by user"
                settings = connector.settings or {}
                settings.pop('current_sync_id', None)
                settings.pop('sync_progress', None)
                connector.settings = settings
                ct = connector.connector_type.value if hasattr(connector.connector_type, 'value') else str(connector.connector_type)
                if ct not in cancelled:
                    cancelled.append(ct)
                print(f"[Cancel-All] Reset DB connector: {ct} SYNCING -> CONNECTED", flush=True)

            if syncing_connectors:
                db.commit()
        except Exception as db_err:
            print(f"[Cancel-All] DB reset error: {db_err}", flush=True)
            if db:
                try:
                    db.rollback()
                except Exception:
                    pass

        print(f"[Cancel-All] Cancelled {len(cancelled)} syncs for tenant {tenant_id}", flush=True)

        return jsonify({
            "success": True,
            "message": f"Cancelled {len(cancelled)} active syncs",
            "cancelled": cancelled
        })

    except Exception as e:
        print(f"[Cancel-All] Error: {e}", flush=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@integration_bp.route('/<connector_type>/sync/cancel', methods=['POST'])
@require_auth
def cancel_sync(connector_type: str):
    """
    Cancel an ongoing sync operation and reset connector status.

    Also resets the database Connector.status from SYNCING back to CONNECTED,
    so the frontend doesn't show a stuck "Syncing" state.

    Response:
    {
        "success": true,
        "message": "Sync cancelled"
    }
    """
    try:
        progress_key = f"{g.tenant_id}:{connector_type}"

        # Cancel in-memory sync progress (if exists)
        if progress_key in sync_progress:
            sync_progress[progress_key] = {
                "status": "cancelled",
                "progress": 0,
                "documents_found": 0,
                "documents_parsed": 0,
                "documents_embedded": 0,
                "current_file": None,
                "error": "Sync cancelled by user"
            }
            print(f"[Cancel] Cancelled in-memory sync progress for {connector_type}", flush=True)

        # Also cancel SSE-based sync progress (if exists)
        try:
            from services.sync_progress_service import get_sync_progress_service
            sps = get_sync_progress_service()
            # Find any active sync for this connector
            for sid, prog in list(sps._progress.items()):
                if prog.get('tenant_id') == str(g.tenant_id) and prog.get('connector_type') == connector_type:
                    sps.update_progress(sid, status='error', stage='Sync cancelled by user', error_message='Cancelled')
                    print(f"[Cancel] Cancelled SSE sync {sid} for {connector_type}", flush=True)
        except Exception as sse_err:
            print(f"[Cancel] SSE cancel error (non-fatal): {sse_err}", flush=True)

        # CRITICAL: Reset DB connector status from SYNCING to CONNECTED
        # This prevents the "stuck syncing" state after failed/cancelled syncs
        db = None
        try:
            # Convert string to enum for DB query
            ct_map = _get_connector_type_map()
            ct_enum = ct_map.get(connector_type)
            if not ct_enum:
                print(f"[Cancel] Unknown connector type: {connector_type}", flush=True)
                return jsonify({"success": True, "message": f"Unknown connector type: {connector_type}"})

            db = get_db()
            connector = db.query(Connector).filter(
                Connector.tenant_id == g.tenant_id,
                Connector.connector_type == ct_enum
            ).first()

            if connector and connector.status == ConnectorStatus.SYNCING:
                connector.status = ConnectorStatus.CONNECTED
                connector.error_message = "Sync cancelled by user"
                # Clear sync-related settings
                settings = connector.settings or {}
                settings.pop('current_sync_id', None)
                settings.pop('sync_progress', None)
                connector.settings = settings
                db.commit()
                print(f"[Cancel] Reset DB connector status: {connector_type} SYNCING -> CONNECTED", flush=True)
            elif connector:
                print(f"[Cancel] Connector {connector_type} status is {connector.status.value}, no reset needed", flush=True)
            else:
                print(f"[Cancel] No connector found for {connector_type}", flush=True)
        except Exception as db_err:
            print(f"[Cancel] DB reset error: {db_err}", flush=True)
            if db:
                try:
                    db.rollback()
                except Exception:
                    pass

        return jsonify({
            "success": True,
            "message": f"{connector_type} sync cancelled and status reset"
        })

    except Exception as e:
        print(f"[Cancel] Error cancelling {connector_type}: {e}", flush=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@integration_bp.route('/<connector_type>/sync/status', methods=['GET'])
@require_auth
def get_sync_status(connector_type: str):
    """
    Get the current sync status for a connector.

    Response:
    {
        "success": true,
        "status": {
            "status": "syncing" | "parsing" | "embedding" | "completed" | "error",
            "progress": 0-100,
            "documents_found": 10,
            "documents_parsed": 5,
            "documents_embedded": 3,
            "current_file": "document.pdf",
            "error": null
        }
    }
    """
    try:
        # First check in-memory progress service (accurate, phase-based)
        from services.sync_progress_service import get_sync_progress_service
        svc = get_sync_progress_service()
        svc_progress = svc.get_active_by_tenant_type(g.tenant_id, connector_type)
        if svc_progress:
            # Map progress service format to polling format
            return jsonify({
                "success": True,
                "status": {
                    "status": svc_progress.get('status', 'syncing'),
                    "progress": svc_progress.get('overall_percent', 0),
                    "overall_percent": svc_progress.get('overall_percent', 0),
                    "documents_found": svc_progress.get('total_items', 0),
                    "documents_parsed": svc_progress.get('processed_items', 0),
                    "documents_embedded": 0,
                    "current_file": svc_progress.get('current_item'),
                    "error": svc_progress.get('error_message')
                }
            })

        # Fallback to old dict
        progress_key = f"{g.tenant_id}:{connector_type}"
        if progress_key in sync_progress:
            status_data = dict(sync_progress[progress_key])
            # Ensure overall_percent is present
            if 'overall_percent' not in status_data:
                status_data['overall_percent'] = status_data.get('progress', 0)
            return jsonify({
                "success": True,
                "status": status_data
            })

        # No active sync, check connector status in DB
        type_map = {
            "gmail": ConnectorType.GMAIL,
            "slack": ConnectorType.SLACK,
            "box": ConnectorType.BOX,
            "github": ConnectorType.GITHUB,
            "pubmed": ConnectorType.PUBMED,
            "webscraper": ConnectorType.WEBSCRAPER,
            "firecrawl": ConnectorType.FIRECRAWL,
            "notion": ConnectorType.NOTION,
            "gdrive": ConnectorType.GOOGLE_DRIVE,
            "zotero": ConnectorType.ZOTERO,
            "onedrive": ConnectorType.ONEDRIVE,
            "quartzy": ConnectorType.QUARTZY
        }

        if connector_type not in type_map:
            return jsonify({
                "success": False,
                "error": f"Invalid connector type: {connector_type}"
            }), 400

        db = get_db()
        try:
            connector = db.query(Connector).filter(
                Connector.tenant_id == g.tenant_id,
                Connector.connector_type == type_map[connector_type],
                Connector.is_active == True
            ).first()

            if connector and connector.status == ConnectorStatus.SYNCING:
                return jsonify({
                    "success": True,
                    "status": {
                        "status": "fetching",
                        "progress": 0,
                        "overall_percent": 0,
                        "documents_found": 0,
                        "documents_parsed": 0,
                        "documents_embedded": 0,
                        "current_file": "Initializing...",
                        "error": None
                    }
                })

            return jsonify({
                "success": True,
                "status": {
                    "status": "idle",
                    "progress": 0,
                    "overall_percent": 0,
                    "documents_found": 0,
                    "documents_parsed": 0,
                    "documents_embedded": 0,
                    "current_file": None,
                    "error": None
                }
            })
        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# DISCONNECT
# ============================================================================

def _get_connector_type_map():
    """Get the mapping of connector type strings to enum values."""
    return {
        "gmail": ConnectorType.GMAIL,
        "slack": ConnectorType.SLACK,
        "box": ConnectorType.BOX,
        "github": ConnectorType.GITHUB,
        "pubmed": ConnectorType.PUBMED,
        "webscraper": ConnectorType.WEBSCRAPER,
        "firecrawl": ConnectorType.FIRECRAWL,
        "notion": ConnectorType.NOTION,
        "gdrive": ConnectorType.GOOGLE_DRIVE,
        "gdocs": ConnectorType.GOOGLE_DOCS,
        "gsheets": ConnectorType.GOOGLE_SHEETS,
        "gslides": ConnectorType.GOOGLE_SLIDES,
        "gcalendar": ConnectorType.GOOGLE_CALENDAR,
        "onedrive": ConnectorType.ONEDRIVE,
        "zotero": ConnectorType.ZOTERO,
        "quartzy": ConnectorType.QUARTZY
    }


def _get_disconnect_counts(db, tenant_id: str, connector_id: str):
    """
    Get counts of items that will be deleted when disconnecting.
    Returns dict with document_count, gap_count, chunk_count.
    """
    from database.models import Document, DocumentChunk, KnowledgeGap

    # Get all document IDs for this connector
    doc_ids = [d.id for d in db.query(Document.id).filter(
        Document.tenant_id == tenant_id,
        Document.connector_id == connector_id,
        Document.is_deleted == False
    ).all()]

    document_count = len(doc_ids)

    # Count chunks
    chunk_count = db.query(DocumentChunk).filter(
        DocumentChunk.document_id.in_(doc_ids)
    ).count() if doc_ids else 0

    # Count knowledge gaps that EXCLUSIVELY reference these documents
    gap_count = 0
    if doc_ids:
        doc_ids_set = set(doc_ids)
        all_gaps = db.query(KnowledgeGap).filter(
            KnowledgeGap.tenant_id == tenant_id
        ).all()

        for gap in all_gaps:
            related_docs = gap.related_document_ids or []
            if related_docs and set(related_docs).issubset(doc_ids_set):
                # All related docs are from this connector - will be deleted
                gap_count += 1

    return {
        "document_count": document_count,
        "chunk_count": chunk_count,
        "gap_count": gap_count
    }


def _cascade_delete_connector_data(db, tenant_id: str, connector_id: str, connector_type: str):
    """
    Delete all data associated with a connector:
    1. Delete embeddings from Pinecone
    2. Delete knowledge gaps that exclusively reference these documents
    3. Delete document chunks
    4. Delete documents
    5. Track deleted external IDs

    Returns dict with deletion counts.
    """
    from database.models import Document, DocumentChunk, KnowledgeGap, DeletedDocument

    # Get all documents for this connector
    documents = db.query(Document).filter(
        Document.tenant_id == tenant_id,
        Document.connector_id == connector_id,
        Document.is_deleted == False
    ).all()

    doc_ids = [doc.id for doc in documents]

    if not doc_ids:
        return {"documents_deleted": 0, "gaps_deleted": 0, "chunks_deleted": 0, "embeddings_deleted": 0}

    print(f"[Disconnect] Cascade deleting {len(doc_ids)} documents for connector {connector_id}")

    # Step 1: Delete from Pinecone
    embeddings_deleted = 0
    try:
        from services.embedding_service import get_embedding_service
        embedding_service = get_embedding_service()
        result = embedding_service.delete_document_embeddings(doc_ids, tenant_id, db)
        embeddings_deleted = result.get('deleted', 0) if result.get('success') else 0
        print(f"[Disconnect] Deleted {embeddings_deleted} embeddings from Pinecone")
    except Exception as e:
        print(f"[Disconnect] Warning: Failed to delete Pinecone embeddings: {e}")

    # Step 2: Delete knowledge gaps that reference these documents
    doc_ids_set = set(str(d) for d in doc_ids)  # Ensure string comparison
    gaps_to_delete = []
    all_gaps = db.query(KnowledgeGap).filter(
        KnowledgeGap.tenant_id == tenant_id
    ).all()

    for gap in all_gaps:
        related_docs = gap.related_document_ids or []
        if not related_docs:
            # Gap has no related docs - check if it was created around the same time as these docs
            # For safety, delete gaps with no document references (orphaned)
            gaps_to_delete.append(gap.id)
        else:
            # Convert to strings for comparison
            related_docs_set = set(str(d) for d in related_docs)
            # Delete if ALL related docs are from this connector (subset check)
            if related_docs_set.issubset(doc_ids_set):
                gaps_to_delete.append(gap.id)
            # Also delete if ANY related doc is from this connector and no docs remain
            elif related_docs_set.intersection(doc_ids_set):
                # Some docs are being deleted - remove those references
                remaining_docs = related_docs_set - doc_ids_set
                if not remaining_docs:
                    gaps_to_delete.append(gap.id)

    gaps_deleted = 0
    if gaps_to_delete:
        gaps_deleted = db.query(KnowledgeGap).filter(
            KnowledgeGap.id.in_(gaps_to_delete)
        ).delete(synchronize_session=False)
        print(f"[Disconnect] Deleted {gaps_deleted} knowledge gaps")

    # Step 3: Delete document chunks
    chunks_deleted = db.query(DocumentChunk).filter(
        DocumentChunk.document_id.in_(doc_ids)
    ).delete(synchronize_session=False)
    print(f"[Disconnect] Deleted {chunks_deleted} document chunks")

    # Step 4: Track deleted external IDs (to prevent re-sync)
    for doc in documents:
        if doc.external_id:
            try:
                deleted_record = DeletedDocument(
                    tenant_id=tenant_id,
                    connector_id=connector_id,
                    external_id=doc.external_id,
                    source_type=doc.source_type,
                    original_title=doc.title
                )
                db.merge(deleted_record)  # Use merge to handle duplicates
            except Exception as e:
                print(f"[Disconnect] Warning: Failed to track deleted doc {doc.external_id}: {e}")

    # Step 5: Delete documents
    documents_deleted = db.query(Document).filter(
        Document.id.in_(doc_ids)
    ).delete(synchronize_session=False)
    print(f"[Disconnect] Deleted {documents_deleted} documents")

    return {
        "documents_deleted": documents_deleted,
        "gaps_deleted": gaps_deleted,
        "chunks_deleted": chunks_deleted,
        "embeddings_deleted": embeddings_deleted
    }


@integration_bp.route('/<connector_type>/disconnect/preview', methods=['GET'])
@require_auth
def disconnect_preview(connector_type: str):
    """
    Preview what will be deleted when disconnecting.
    Returns counts of documents, knowledge gaps, etc.
    """
    try:
        type_map = _get_connector_type_map()

        if connector_type not in type_map:
            return jsonify({
                "success": False,
                "error": f"Invalid connector type: {connector_type}"
            }), 400

        db = get_db()
        try:
            connector = db.query(Connector).filter(
                Connector.tenant_id == g.tenant_id,
                Connector.connector_type == type_map[connector_type]
            ).first()

            if not connector:
                return jsonify({
                    "success": False,
                    "error": f"{connector_type.title()} not connected"
                }), 400

            counts = _get_disconnect_counts(db, g.tenant_id, connector.id)

            return jsonify({
                "success": True,
                "connector_type": connector_type,
                "counts": counts,
                "warning": f"Disconnecting will permanently delete {counts['document_count']} documents, {counts['gap_count']} knowledge gaps, and all associated embeddings."
            })

        finally:
            db.close()

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@integration_bp.route('/<connector_type>/disconnect', methods=['POST'])
@require_auth
def disconnect_connector(connector_type: str):
    """
    Disconnect an integration and delete all associated data.

    This will:
    1. Delete all documents from this integration
    2. Delete embeddings from Pinecone
    3. Delete knowledge gaps that exclusively reference these documents
    4. Mark the connector as disconnected

    Request body (optional):
    {
        "confirm": true  // Required to proceed with deletion
    }
    """
    try:
        type_map = _get_connector_type_map()

        if connector_type not in type_map:
            return jsonify({
                "success": False,
                "error": f"Invalid connector type: {connector_type}"
            }), 400

        data = request.get_json() or {}
        confirmed = data.get('confirm', False)

        db = get_db()
        try:
            connector = db.query(Connector).filter(
                Connector.tenant_id == g.tenant_id,
                Connector.connector_type == type_map[connector_type]
            ).first()

            if not connector:
                return jsonify({
                    "success": False,
                    "error": f"{connector_type.title()} not connected"
                }), 400

            # Get counts first
            counts = _get_disconnect_counts(db, g.tenant_id, connector.id)

            # If there's data and not confirmed, return warning
            if (counts['document_count'] > 0 or counts['gap_count'] > 0) and not confirmed:
                return jsonify({
                    "success": False,
                    "requires_confirmation": True,
                    "counts": counts,
                    "warning": f"This will permanently delete {counts['document_count']} documents and {counts['gap_count']} knowledge gaps. Send confirm: true to proceed."
                }), 400

            # Cascade delete all data
            deletion_result = _cascade_delete_connector_data(
                db, g.tenant_id, connector.id, connector_type
            )

            # Disconnect the connector
            connector.is_active = False
            connector.status = ConnectorStatus.DISCONNECTED
            connector.access_token = None
            connector.refresh_token = None

            db.commit()

            return jsonify({
                "success": True,
                "message": f"{connector_type.title()} disconnected",
                "deleted": deletion_result
            })

        finally:
            db.close()

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# STATUS
# ============================================================================

@integration_bp.route('/<connector_type>/status', methods=['GET'])
@require_auth
def connector_status(connector_type: str):
    """
    Get detailed status for a connector.
    """
    try:
        type_map = {
            "gmail": ConnectorType.GMAIL,
            "slack": ConnectorType.SLACK,
            "box": ConnectorType.BOX,
            "github": ConnectorType.GITHUB,
            "pubmed": ConnectorType.PUBMED,
            "webscraper": ConnectorType.WEBSCRAPER,
            "firecrawl": ConnectorType.FIRECRAWL,
            "notion": ConnectorType.NOTION,
            "gdrive": ConnectorType.GOOGLE_DRIVE,
            "gdocs": ConnectorType.GOOGLE_DOCS,
            "gsheets": ConnectorType.GOOGLE_SHEETS,
            "gslides": ConnectorType.GOOGLE_SLIDES,
            "gcalendar": ConnectorType.GOOGLE_CALENDAR,
            "quartzy": ConnectorType.QUARTZY
        }

        if connector_type not in type_map:
            return jsonify({
                "success": False,
                "error": f"Invalid connector type: {connector_type}"
            }), 400

        db = get_db()
        try:
            connector = db.query(Connector).filter(
                Connector.tenant_id == g.tenant_id,
                Connector.connector_type == type_map[connector_type],
                Connector.is_active == True
            ).first()

            if not connector:
                return jsonify({
                    "success": True,
                    "status": "not_configured",
                    "connector": None
                })

            return jsonify({
                "success": True,
                "status": connector.status.value,
                "connector": connector.to_dict(include_tokens=False)
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# SETTINGS
# ============================================================================

@integration_bp.route('/<connector_type>/settings', methods=['PUT'])
@require_auth
def update_connector_settings(connector_type: str):
    """
    Update connector settings.

    Request body:
    {
        "settings": {
            "folder_ids": ["123", "456"],
            "max_file_size_mb": 100,
            ...
        }
    }
    """
    try:
        type_map = {
            "gmail": ConnectorType.GMAIL,
            "slack": ConnectorType.SLACK,
            "box": ConnectorType.BOX,
            "github": ConnectorType.GITHUB,
            "pubmed": ConnectorType.PUBMED,
            "webscraper": ConnectorType.WEBSCRAPER,
            "firecrawl": ConnectorType.FIRECRAWL,
            "notion": ConnectorType.NOTION,
            "gdrive": ConnectorType.GOOGLE_DRIVE,
            "gdocs": ConnectorType.GOOGLE_DOCS,
            "gsheets": ConnectorType.GOOGLE_SHEETS,
            "gslides": ConnectorType.GOOGLE_SLIDES,
            "gcalendar": ConnectorType.GOOGLE_CALENDAR,
            "quartzy": ConnectorType.QUARTZY
        }

        if connector_type not in type_map:
            return jsonify({
                "success": False,
                "error": f"Invalid connector type: {connector_type}"
            }), 400

        data = request.get_json()
        if not data or 'settings' not in data:
            return jsonify({
                "success": False,
                "error": "Settings required"
            }), 400

        db = get_db()
        try:
            connector = db.query(Connector).filter(
                Connector.tenant_id == g.tenant_id,
                Connector.connector_type == type_map[connector_type],
                Connector.is_active == True
            ).first()

            if not connector:
                return jsonify({
                    "success": False,
                    "error": f"{connector_type.title()} not configured"
                }), 400

            # Merge settings
            current_settings = connector.settings or {}
            connector.settings = {**current_settings, **data['settings']}
            connector.updated_at = utc_now()

            db.commit()

            return jsonify({
                "success": True,
                "connector": connector.to_dict()
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# ZOTERO INTEGRATION (OAuth 1.0a)
# ============================================================================

# Zotero OAuth 1.0a state is stored in DATABASE (not session/memory)
# This works across multiple instances because state is persisted in PostgreSQL
# We use a pending Connector entry with the oauth_token stored in settings

@integration_bp.route('/zotero/auth', methods=['GET'])
@require_auth
def zotero_auth():
    """
    Start Zotero OAuth 1.0a flow.

    Zotero uses OAuth 1.0a which requires:
    1. Get request token
    2. Redirect user to authorize
    3. User approves, Zotero redirects to callback with verifier
    4. Exchange verifier for access token (which is the permanent API key)

    Note: OAuth 1.0a doesn't pass back custom query params like 'state',
    so we store the pending state in the DATABASE for the callback.
    """
    import traceback

    try:
        print("[ZoteroAuth] Starting Zotero OAuth 1.0a flow...", flush=True)

        # Check for required environment variables first
        client_key = os.getenv("ZOTERO_CLIENT_KEY", "")
        client_secret = os.getenv("ZOTERO_CLIENT_SECRET", "")

        if not client_key or not client_secret:
            print("[ZoteroAuth] Missing ZOTERO_CLIENT_KEY or ZOTERO_CLIENT_SECRET", flush=True)
            return jsonify({
                "success": False,
                "error": "Zotero OAuth credentials not configured. Please set ZOTERO_CLIENT_KEY and ZOTERO_CLIENT_SECRET environment variables."
            }), 500

        # Check if requests-oauthlib is installed
        try:
            from requests_oauthlib import OAuth1Session
            print("[ZoteroAuth] requests-oauthlib is available", flush=True)
        except ImportError as ie:
            print(f"[ZoteroAuth] requests-oauthlib not installed: {ie}", flush=True)
            return jsonify({
                "success": False,
                "error": "requests-oauthlib not installed. Please add it to requirements.txt"
            }), 500

        # Now import the connector
        try:
            from connectors.zotero_connector import ZoteroConnector
            print("[ZoteroAuth] ZoteroConnector imported successfully", flush=True)
        except ImportError as ie:
            print(f"[ZoteroAuth] Failed to import ZoteroConnector: {ie}", flush=True)
            print(f"[ZoteroAuth] Traceback: {traceback.format_exc()}", flush=True)
            return jsonify({
                "success": False,
                "error": f"Failed to import ZoteroConnector: {str(ie)}"
            }), 500

        # Build callback URL
        if os.getenv("ZOTERO_REDIRECT_URI"):
            callback_url = os.getenv("ZOTERO_REDIRECT_URI")
        else:
            # Use BACKEND_URL if set, otherwise derive from request
            backend_url = os.getenv("BACKEND_URL")
            if backend_url:
                host = backend_url.rstrip('/')
            else:
                host = request.host_url.rstrip('/')
                # Ensure HTTPS for production (Render/Heroku behind load balancers)
                if host.startswith('http://') and 'localhost' not in host:
                    host = host.replace('http://', 'https://', 1)
            callback_url = f"{host}/api/integrations/zotero/callback"

        print(f"[ZoteroAuth] Callback URL: {callback_url}", flush=True)

        # Get request token and authorization URL
        try:
            request_token, auth_url, error = ZoteroConnector.get_oauth_session(callback_url)
            print(f"[ZoteroAuth] get_oauth_session returned: token={bool(request_token)}, url={bool(auth_url)}, error={error}", flush=True)
        except Exception as oauth_err:
            print(f"[ZoteroAuth] get_oauth_session exception: {oauth_err}", flush=True)
            print(f"[ZoteroAuth] Traceback: {traceback.format_exc()}", flush=True)
            return jsonify({
                "success": False,
                "error": f"OAuth session error: {str(oauth_err)}"
            }), 500

        if error:
            print(f"[ZoteroAuth] Error from get_oauth_session: {error}", flush=True)
            return jsonify({
                "success": False,
                "error": error
            }), 500

        if not request_token or not auth_url:
            print("[ZoteroAuth] No request_token or auth_url returned", flush=True)
            return jsonify({
                "success": False,
                "error": "Failed to get OAuth request token from Zotero"
            }), 500

        # Store pending OAuth state in DATABASE (works across multiple instances)
        # We create/update a Connector entry with status=PENDING and store the oauth secrets
        db = get_db()
        try:
            # Look for existing pending or active Zotero connector
            connector = db.query(Connector).filter(
                Connector.tenant_id == g.tenant_id,
                Connector.connector_type == ConnectorType.ZOTERO
            ).first()

            pending_state = {
                "oauth_token": request_token['oauth_token'],
                "oauth_token_secret": request_token['oauth_token_secret'],
                "user_id": g.user_id,
                "callback_url": callback_url,
                "timestamp": time.time()
            }

            if connector:
                # Update existing connector with pending state
                connector.settings = {
                    **(connector.settings or {}),
                    "pending_oauth": pending_state
                }
                connector.status = ConnectorStatus.CONNECTING
            else:
                # Create new pending connector
                connector = Connector(
                    id=generate_uuid(),
                    tenant_id=g.tenant_id,
                    connector_type=ConnectorType.ZOTERO,
                    name="Zotero",
                    status=ConnectorStatus.CONNECTING,
                    is_active=False,  # Not active until OAuth completes
                    settings={"pending_oauth": pending_state}
                )
                db.add(connector)

            db.commit()
            print(f"[ZoteroAuth] Pending OAuth state stored in database", flush=True)

        finally:
            db.close()

        print(f"[ZoteroAuth] Auth URL generated successfully", flush=True)

        return jsonify({
            "success": True,
            "auth_url": auth_url
        })

    except Exception as e:
        print(f"[ZoteroAuth] Unexpected exception: {e}", flush=True)
        print(f"[ZoteroAuth] Traceback: {traceback.format_exc()}", flush=True)
        return jsonify({
            "success": False,
            "error": f"Unexpected error: {str(e)}"
        }), 500


@integration_bp.route('/zotero/callback', methods=['GET'])
def zotero_callback():
    """
    Zotero OAuth 1.0a callback handler.

    Receives oauth_token and oauth_verifier from Zotero after user approves.
    Exchanges these for a permanent API key.

    Note: We retrieve the pending state from DATABASE using oauth_token as key.
    """
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

    try:
        from connectors.zotero_connector import ZoteroConnector

        # Get OAuth parameters from callback
        oauth_token = request.args.get('oauth_token')
        oauth_verifier = request.args.get('oauth_verifier')

        print(f"[Zotero Callback] oauth_token={oauth_token[:20] if oauth_token else None}..., verifier present: {bool(oauth_verifier)}", flush=True)

        if not oauth_token or not oauth_verifier:
            return safe_error_redirect(f"{FRONTEND_URL}/integrations", "missing_oauth_params")

        # Look up pending OAuth state from DATABASE
        db = get_db()
        try:
            # Find connector with matching pending oauth_token
            from sqlalchemy import cast
            from sqlalchemy.dialects.postgresql import JSONB

            # Query all pending Zotero connectors and check oauth_token
            pending_connectors = db.query(Connector).filter(
                Connector.connector_type == ConnectorType.ZOTERO,
                Connector.status == ConnectorStatus.CONNECTING
            ).all()

            connector = None
            pending_state = None
            for c in pending_connectors:
                if c.settings and c.settings.get("pending_oauth", {}).get("oauth_token") == oauth_token:
                    connector = c
                    pending_state = c.settings.get("pending_oauth")
                    break

            if not connector or not pending_state:
                print(f"[Zotero Callback] No pending connector found for oauth_token", flush=True)
                return safe_error_redirect(f"{FRONTEND_URL}/integrations", "expired_or_missing_state")

            # Check if state is expired (10 minute timeout)
            timestamp = pending_state.get("timestamp", 0)
            if time.time() - timestamp > 600:
                print(f"[Zotero Callback] Pending state expired", flush=True)
                return safe_error_redirect(f"{FRONTEND_URL}/integrations", "state_expired")

            oauth_token_secret = pending_state.get("oauth_token_secret")
            tenant_id = connector.tenant_id
            user_id = pending_state.get("user_id")

            print(f"[Zotero Callback] Found pending state for tenant: {tenant_id}", flush=True)

            if not oauth_token_secret:
                return safe_error_redirect(f"{FRONTEND_URL}/integrations", "missing_token_secret")

            # Exchange verifier for access token
            credentials, error = ZoteroConnector.exchange_verifier_for_token(
                oauth_token=oauth_token,
                oauth_token_secret=oauth_token_secret,
                oauth_verifier=oauth_verifier
            )

            if error:
                print(f"[Zotero Callback] Token exchange failed: {error}", flush=True)
                return safe_error_redirect(f"{FRONTEND_URL}/integrations", f"token_exchange_failed: {error}")

            api_key = credentials.get('api_key')
            zotero_user_id = credentials.get('user_id')
            username = credentials.get('username', 'Zotero User')

            print(f"[Zotero Callback] Got API key for user: {username}", flush=True)

            # Update the connector with actual credentials (same db session)
            # Remove pending_oauth and set real credentials
            new_settings = {k: v for k, v in (connector.settings or {}).items() if k not in ("pending_oauth", "library_version")}
            new_settings["zotero_user_id"] = zotero_user_id
            new_settings["username"] = username
            new_settings["sync_pdfs"] = True

            connector.access_token = api_key
            connector.settings = new_settings
            connector.status = ConnectorStatus.CONNECTED
            connector.is_active = True
            connector.name = f"Zotero - {username}"
            connector.error_message = None
            connector.updated_at = utc_now()

            db.commit()
            print(f"[Zotero Callback] Connector saved successfully", flush=True)

        finally:
            db.close()

        return redirect(f"{FRONTEND_URL}/integrations?success=zotero")

    except Exception as e:
        import traceback
        print(f"[Zotero Callback] Exception: {e}", flush=True)
        print(f"[Zotero Callback] Traceback: {traceback.format_exc()}", flush=True)
        return safe_error_redirect(f"{FRONTEND_URL}/integrations", str(e))


@integration_bp.route('/zotero/sync', methods=['POST'])
@require_auth
def zotero_sync():
    """
    Sync Zotero library with background threading and SSE progress tracking.

    Fetches all items (papers, books, etc.) from the user's Zotero library,
    downloads PDFs, and stores them as documents.

    Uses same pattern as Slack/Gmail - returns immediately and runs sync in background.
    Frontend can poll /zotero/sync/status for progress.
    """
    try:
        from services.sync_progress_service import get_sync_progress_service

        print(f"[Zotero Sync] Starting sync for tenant: {g.tenant_id}", flush=True)

        # Capture context for background thread (use IDs, not objects)
        tenant_id = g.tenant_id
        user_id = g.user_id

        db = get_db()
        try:
            connector = db.query(Connector).filter(
                Connector.tenant_id == tenant_id,
                Connector.connector_type == ConnectorType.ZOTERO,
                Connector.is_active == True
            ).first()

            if not connector:
                return jsonify({
                    "success": False,
                    "error": "Zotero not connected"
                }), 400

            if not connector.access_token:
                return jsonify({
                    "success": False,
                    "error": "Zotero API key missing"
                }), 400

            # Get connector ID and credentials before closing session
            connector_id = connector.id
            access_token = connector.access_token
            zotero_user_id = connector.settings.get("zotero_user_id")
            settings = connector.settings.copy() if connector.settings else {}

            # Check if we have any ACTIVE (non-deleted) Zotero documents - if not, force full sync
            zotero_doc_count = db.query(Document).filter(
                Document.tenant_id == tenant_id,
                Document.connector_id == connector_id,
                Document.is_deleted == False  # Only count non-deleted documents
            ).count()

            print(f"[Zotero Sync] Active Zotero document count: {zotero_doc_count}, library_version: {settings.get('library_version')}", flush=True)

            if zotero_doc_count == 0 and settings.get("library_version"):
                print(f"[Zotero Sync] No active documents found, clearing library_version for full sync", flush=True)
                settings.pop("library_version", None)
                # Also update the connector in DB
                connector.settings = {k: v for k, v in (connector.settings or {}).items() if k != "library_version"}
                db.commit()
                print(f"[Zotero Sync] library_version cleared from connector settings", flush=True)

        finally:
            db.close()

        # Start progress tracking
        progress_service = get_sync_progress_service()
        sync_id = progress_service.start_sync(tenant_id, user_id, 'zotero')

        # Store sync_id in connector for cross-worker access
        db = get_db()
        try:
            connector = db.query(Connector).filter(
                Connector.id == connector_id
            ).first()
            if connector:
                connector.settings = {
                    **(connector.settings or {}),
                    "current_sync_id": sync_id,
                    "sync_started_at": utc_now().isoformat()
                }
                connector.status = ConnectorStatus.SYNCING
                db.commit()
                print(f"[Zotero Sync] Stored sync_id {sync_id} in connector", flush=True)
        finally:
            db.close()

        # Initialize progress dict for legacy frontend polling
        progress_key = f"{tenant_id}:zotero"
        sync_progress[progress_key] = {
            "status": "syncing",
            "progress": 5,
            "documents_found": 0,
            "documents_parsed": 0,
            "documents_embedded": 0,
            "current_file": "Initializing Zotero sync...",
            "stage": "starting",
            "connector_type": "zotero"
        }

        # Start background thread for sync
        def _run_zotero_sync_background():
            """Background sync function with progress tracking"""
            print(f"[Zotero Sync BG] === BACKGROUND THREAD STARTED ===", flush=True)

            try:
                from connectors.zotero_connector import ZoteroConnector
                from connectors.base_connector import ConnectorConfig
                from services.embedding_service import get_embedding_service
                from services.extraction_service import get_extraction_service

                # Update progress - connecting
                sync_progress[progress_key]["progress"] = 10
                sync_progress[progress_key]["current_file"] = "Connecting to Zotero..."
                progress_service.update_progress(sync_id, status='connecting', stage='Connecting to Zotero...')

                # Create connector config
                config = ConnectorConfig(
                    connector_type="zotero",
                    user_id=user_id,
                    credentials={
                        "api_key": access_token,
                        "user_id": zotero_user_id,
                        "username": settings.get("username")  # Pass username for web URLs
                    },
                    settings=settings
                )

                # Create connector and sync
                zotero_connector = ZoteroConnector(config)

                # Update progress - fetching
                sync_progress[progress_key]["progress"] = 20
                sync_progress[progress_key]["current_file"] = "Fetching Zotero library..."
                sync_progress[progress_key]["status"] = "syncing"
                progress_service.update_progress(sync_id, status='syncing', stage='Fetching Zotero library items...')

                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    documents = loop.run_until_complete(zotero_connector.sync())
                finally:
                    loop.close()

                print(f"[Zotero Sync BG] Got {len(documents)} documents", flush=True)

                # Update progress - documents found
                sync_progress[progress_key]["documents_found"] = len(documents)
                sync_progress[progress_key]["progress"] = 40
                sync_progress[progress_key]["status"] = "parsing"
                progress_service.update_progress(
                    sync_id,
                    status='parsing',
                    stage=f'Processing {len(documents)} Zotero items...',
                    total_items=len(documents)
                )

                # Update connector in DB for cross-worker progress visibility
                try:
                    db_prog = get_db()
                    conn = db_prog.query(Connector).filter(Connector.id == connector_id).first()
                    if conn:
                        conn.settings = {
                            **(conn.settings or {}),
                            "sync_progress": {
                                "total_items": len(documents),
                                "processed_items": 0,
                                "status": "parsing",
                                "stage": f"Processing {len(documents)} items..."
                            }
                        }
                        db_prog.commit()
                    db_prog.close()
                except Exception as db_err:
                    print(f"[Zotero Sync BG] DB progress update error: {db_err}", flush=True)

                if not documents:
                    # No documents to sync
                    sync_progress[progress_key]["status"] = "completed"
                    sync_progress[progress_key]["progress"] = 100
                    sync_progress[progress_key]["message"] = "No new documents found in Zotero library"
                    progress_service.complete_sync(sync_id)
                    print(f"[Zotero Sync BG] No documents to sync", flush=True)
                    return

                # Store documents in database
                db = get_db()
                try:
                    docs_created = 0
                    docs_updated = 0
                    doc_ids = []

                    connector = db.query(Connector).filter(
                        Connector.id == connector_id
                    ).first()

                    if not connector:
                        raise Exception("Connector not found")

                    # Update connector status to syncing
                    connector.status = ConnectorStatus.SYNCING
                    db.commit()

                    total_docs = len(documents)
                    for i, doc in enumerate(documents):
                        # Update progress
                        parse_progress = 40 + int((i / total_docs) * 30)
                        sync_progress[progress_key]["progress"] = parse_progress
                        sync_progress[progress_key]["documents_parsed"] = i + 1
                        current_doc_name = doc.title[:50] if doc.title else f"Document {i+1}"
                        sync_progress[progress_key]["current_file"] = current_doc_name
                        progress_service.increment_processed(sync_id, current_item=current_doc_name)

                        # Look for existing document (only non-deleted ones)
                        existing = db.query(Document).filter(
                            Document.tenant_id == tenant_id,
                            Document.external_id == doc.doc_id,
                            Document.is_deleted == False
                        ).first()

                        if existing:
                            # Update existing document
                            existing.title = doc.title
                            existing.content = doc.content
                            existing.doc_metadata = doc.metadata
                            existing.source_url = doc.url  # Add external link
                            existing.updated_at = utc_now()
                            docs_updated += 1
                            doc_ids.append(existing.id)
                        else:
                            # Create
                            new_doc_id = generate_uuid()
                            new_doc = Document(
                                id=new_doc_id,
                                tenant_id=tenant_id,
                                connector_id=connector.id,
                                external_id=doc.doc_id,
                                source_type="zotero",
                                title=doc.title,
                                content=doc.content,
                                sender=doc.author,
                                source_url=doc.url,  # Add external link
                                source_created_at=doc.timestamp,
                                doc_metadata=doc.metadata,
                                status=DocumentStatus.PENDING,
                                classification=DocumentClassification.WORK,
                                is_deleted=False
                            )
                            db.add(new_doc)
                            docs_created += 1
                            doc_ids.append(new_doc_id)

                        # Commit in batches
                        if (i + 1) % 50 == 0:
                            db.commit()
                            print(f"[Zotero Sync BG] Committed batch at {i + 1}/{total_docs}", flush=True)

                    # Final commit
                    db.commit()
                    print(f"[Zotero Sync BG] All documents saved: {docs_created} created, {docs_updated} updated", flush=True)

                    # Update progress - embedding phase
                    sync_progress[progress_key]["status"] = "embedding"
                    sync_progress[progress_key]["progress"] = 75
                    sync_progress[progress_key]["current_file"] = "Creating embeddings..."
                    progress_service.update_progress(sync_id, status='embedding', stage='Creating embeddings for Zotero documents...')

                    # Embed documents to Pinecone
                    try:
                        if doc_ids:
                            docs_to_embed = db.query(Document).filter(
                                Document.id.in_(doc_ids),
                                Document.tenant_id == tenant_id
                            ).all()

                            # Extract structured summaries
                            sync_progress[progress_key]["current_file"] = "Extracting document summaries..."
                            sync_progress[progress_key]["progress"] = 85
                            try:
                                extraction_service = get_extraction_service()
                                extract_result = extraction_service.extract_documents(
                                    documents=docs_to_embed,
                                    db=db,
                                    force=False
                                )
                                sync_progress[progress_key]["documents_extracted"] = extract_result.get('extracted', 0)
                                print(f"[Zotero Sync BG] Extracted summaries for {extract_result.get('extracted', 0)} documents", flush=True)
                            except Exception as extract_error:
                                print(f"[Zotero Sync BG] EXTRACTION ERROR: {extract_error}", flush=True)

                            # Embed to Pinecone
                            sync_progress[progress_key]["current_file"] = "Embedding documents..."
                            sync_progress[progress_key]["progress"] = 90

                            embedding_service = get_embedding_service()
                            embed_result = embedding_service.embed_documents(
                                documents=docs_to_embed,
                                tenant_id=tenant_id,
                                db=db,
                                force_reembed=False
                            )

                            sync_progress[progress_key]["documents_embedded"] = embed_result.get('embedded', 0)
                            sync_progress[progress_key]["chunks_created"] = embed_result.get('chunks', 0)
                            print(f"[Zotero Sync BG] Embedding result: embedded={embed_result.get('embedded', 0)}, chunks={embed_result.get('chunks', 0)}", flush=True)

                    except Exception as embed_error:
                        print(f"[Zotero Sync BG] EMBEDDING ERROR: {embed_error}", flush=True)
                        import traceback
                        traceback.print_exc()
                        sync_progress[progress_key]["embedding_error"] = str(embed_error)

                    # Update connector status
                    connector.status = ConnectorStatus.CONNECTED
                    connector.last_sync_at = utc_now()
                    connector.last_sync_status = "success"
                    connector.last_sync_items_count = len(documents)
                    connector.total_items_synced = (connector.total_items_synced or 0) + docs_created

                    # Save library version for incremental sync
                    if config.settings.get("library_version"):
                        connector.sync_cursor = config.settings["library_version"]
                        connector.settings = {
                            **(connector.settings or {}),
                            "library_version": config.settings["library_version"]
                        }

                    db.commit()

                    # Mark complete
                    sync_progress[progress_key]["status"] = "completed"
                    sync_progress[progress_key]["progress"] = 100
                    sync_progress[progress_key]["current_file"] = None
                    progress_service.complete_sync(sync_id)

                    print(f"[Zotero Sync BG] === SYNC COMPLETE: {docs_created} created, {docs_updated} updated ===", flush=True)

                finally:
                    db.close()

            except Exception as e:
                import traceback
                print(f"[Zotero Sync BG] FATAL ERROR: {e}", flush=True)
                traceback.print_exc()

                sync_progress[progress_key]["status"] = "error"
                sync_progress[progress_key]["error"] = str(e)
                progress_service.complete_sync(sync_id, error_message=str(e))

                # Try to update connector status
                try:
                    db = get_db()
                    try:
                        connector = db.query(Connector).filter(
                            Connector.id == connector_id
                        ).first()
                        if connector:
                            connector.status = ConnectorStatus.ERROR
                            connector.last_sync_status = "error"
                            connector.error_message = str(e)
                            db.commit()
                    finally:
                        db.close()
                except Exception:
                    pass

        # Start background thread
        thread = threading.Thread(target=_run_zotero_sync_background)
        thread.daemon = True
        thread.start()

        print(f"[Zotero Sync] Background thread started, returning immediately", flush=True)

        # Return initial progress for frontend (helps with multi-worker deployments)
        initial_progress = {
            "sync_id": sync_id,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "connector_type": "zotero",
            "status": "connecting",
            "stage": "Connecting to service...",
            "total_items": 0,
            "processed_items": 0,
            "failed_items": 0,
            "current_item": None,
            "error_message": None,
            "percent_complete": 0
        }

        return jsonify({
            "success": True,
            "message": "Zotero sync started in background",
            "sync_id": sync_id,
            "progress": initial_progress
        })

    except Exception as e:
        import traceback
        print(f"[Zotero Sync] Error starting sync: {e}", flush=True)
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@integration_bp.route('/zotero/status', methods=['GET'])
@require_auth
def zotero_status():
    """Get Zotero connection status."""
    try:
        db = get_db()
        try:
            connector = db.query(Connector).filter(
                Connector.tenant_id == g.tenant_id,
                Connector.connector_type == ConnectorType.ZOTERO,
                Connector.is_active == True
            ).first()

            if not connector:
                return jsonify({
                    "success": True,
                    "connected": False,
                    "status": "not_configured"
                })

            return jsonify({
                "success": True,
                "connected": connector.status == ConnectorStatus.CONNECTED,
                "status": connector.status.value if connector.status else "unknown",
                "username": connector.settings.get("username") if connector.settings else None,
                "last_sync": connector.last_sync_at.isoformat() if connector.last_sync_at else None,
                "items_synced": connector.total_items_synced or 0
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@integration_bp.route('/zotero/disconnect', methods=['POST'])
@require_auth
def zotero_disconnect():
    """Disconnect Zotero integration."""
    try:
        db = get_db()
        try:
            connector = db.query(Connector).filter(
                Connector.tenant_id == g.tenant_id,
                Connector.connector_type == ConnectorType.ZOTERO
            ).first()

            if connector:
                connector.is_active = False
                connector.status = ConnectorStatus.DISCONNECTED
                connector.access_token = None
                connector.updated_at = utc_now()
                db.commit()

            return jsonify({
                "success": True,
                "message": "Zotero disconnected"
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
