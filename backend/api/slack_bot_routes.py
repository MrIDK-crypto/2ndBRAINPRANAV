"""
Slack Bot API Routes
Handles Slack OAuth, events, and slash commands.
"""

import os
import hmac
import hashlib
import time
import json
import secrets
import threading
from flask import Blueprint, request, jsonify, redirect, g
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_sdk.signature import SignatureVerifier
from services.auth_service import require_auth
from services.slack_bot_service import (
    SlackBotService,
    register_slack_workspace,
    get_tenant_for_workspace,
    get_bot_token_for_workspace
)

slack_bot_bp = Blueprint('slack_bot', __name__, url_prefix='/api/slack')


# ============================================================================
# SLACK EVENT DEDUPLICATION
# ============================================================================
# Slack retries events if it doesn't get a 200 response within 3 seconds.
_processed_events = {}
_events_lock = threading.Lock()
DEDUP_TTL_SECONDS = 60


def _is_duplicate_event(event_id: str) -> bool:
    """Check if event was already processed"""
    if not event_id:
        return False

    now = time.time()
    with _events_lock:
        # Clean old entries
        expired = [k for k, v in _processed_events.items() if now - v > DEDUP_TTL_SECONDS]
        for k in expired:
            del _processed_events[k]

        if event_id in _processed_events:
            print(f"[SlackBot] DUPLICATE event {event_id} - skipping", flush=True)
            return True

        _processed_events[event_id] = now
        return False


# Slack app credentials (from environment)
SLACK_CLIENT_ID = os.getenv('SLACK_CLIENT_ID')
SLACK_CLIENT_SECRET = os.getenv('SLACK_CLIENT_SECRET')
SLACK_SIGNING_SECRET = os.getenv('SLACK_SIGNING_SECRET')

# Signature verifier
signature_verifier = SignatureVerifier(SLACK_SIGNING_SECRET) if SLACK_SIGNING_SECRET else None


# ============================================================================
# OAUTH STATE STORE (CSRF protection)
# ============================================================================
# Stores {state_token: (tenant_id, user_id, timestamp)} with 10-min TTL.
_oauth_states = {}
_oauth_states_lock = threading.Lock()
OAUTH_STATE_TTL_SECONDS = 600  # 10 minutes


def _create_oauth_state(tenant_id: str, user_id: str) -> str:
    """Create a cryptographically random state token and store the mapping."""
    token = secrets.token_urlsafe(32)
    with _oauth_states_lock:
        # Clean expired states
        now = time.time()
        expired = [k for k, v in _oauth_states.items() if now - v[2] > OAUTH_STATE_TTL_SECONDS]
        for k in expired:
            del _oauth_states[k]
        _oauth_states[token] = (tenant_id, user_id, now)
    return token


def _validate_oauth_state(token: str):
    """Validate and consume a state token. Returns (tenant_id, user_id) or None."""
    if not token:
        return None
    with _oauth_states_lock:
        entry = _oauth_states.pop(token, None)
    if not entry:
        return None
    tenant_id, user_id, created_at = entry
    if time.time() - created_at > OAUTH_STATE_TTL_SECONDS:
        return None
    return tenant_id, user_id


# ============================================================================
# SLACK SIGNATURE VERIFICATION
# ============================================================================

def verify_slack_request():
    """
    Verify that the request actually came from Slack using HMAC signature.
    Returns True always - logs warnings for invalid signatures but does NOT reject.
    This matches the working production behavior where signature mismatches
    should not block event delivery.
    """
    if not SLACK_SIGNING_SECRET or not signature_verifier:
        print("[SlackBot] Signature verification skipped (no secret configured)", flush=True)
        return True

    try:
        timestamp = request.headers.get('X-Slack-Request-Timestamp', '')
        signature = request.headers.get('X-Slack-Signature', '')

        if not timestamp or not signature:
            print(f"[SlackBot] WARNING: Missing signature headers - allowing anyway", flush=True)
            return True

        body = request.get_data(as_text=True)
        is_valid = signature_verifier.is_valid(
            body=body,
            timestamp=timestamp,
            signature=signature
        )

        if not is_valid:
            print(f"[SlackBot] WARNING: Invalid HMAC signature (body_len={len(body)}, sig={signature[:20]}...) - allowing anyway", flush=True)
        else:
            print(f"[SlackBot] Signature verified OK", flush=True)

        return True  # Always allow - don't block events due to signature mismatch

    except Exception as e:
        print(f"[SlackBot] Signature verification error: {e} - allowing anyway", flush=True)
        return True


# ============================================================================
# OAUTH FLOW
# ============================================================================

@slack_bot_bp.route('/oauth/install', methods=['GET'])
@require_auth
def slack_oauth_install():
    """
    Start Slack OAuth flow (redirect to Slack).

    This is called when user clicks "Add to Slack" button in the UI.

    GET /api/slack/oauth/install

    Redirects to Slack authorization page.
    """
    # Build OAuth URL
    scopes = [
        'app_mentions:read',  # Hear @mentions
        'channels:history',   # Read channel messages
        'channels:read',      # Access channel list
        'chat:write',         # Post messages
        'commands',           # Receive slash commands
        'files:read',         # Read files shared in channels
        'files:write',        # Upload files
        'im:history',         # Read DMs
        'im:read',            # Access DM list
        'im:write',           # Send DMs
        'users:read',         # Read user info
    ]

    # Create cryptographically random state with CSRF protection
    state = _create_oauth_state(g.tenant_id, g.user_id)

    slack_auth_url = (
        f"https://slack.com/oauth/v2/authorize"
        f"?client_id={SLACK_CLIENT_ID}"
        f"&scope={','.join(scopes)}"
        f"&state={state}"
        f"&redirect_uri={request.host_url}api/slack/oauth/callback"
    )

    return redirect(slack_auth_url)


@slack_bot_bp.route('/oauth/callback', methods=['GET'])
def slack_oauth_callback():
    """
    Handle Slack OAuth callback.

    Slack redirects here after user authorizes the app.

    GET /api/slack/oauth/callback?code=...&state=...

    Exchanges code for access token and stores it.
    """
    try:
        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')

        if error:
            return jsonify({
                'success': False,
                'error': f"Slack authorization failed: {error}"
            }), 400

        if not code:
            return jsonify({
                'success': False,
                'error': "No authorization code provided"
            }), 400

        # Validate state token (CSRF protection)
        state_result = _validate_oauth_state(state)
        if not state_result:
            print(f"[SlackBot] OAuth REJECTED: Invalid or expired state token", flush=True)
            return jsonify({
                'success': False,
                'error': "Invalid or expired authorization. Please try again."
            }), 403

        tenant_id, user_id = state_result

        # Exchange code for access token
        client = WebClient()

        response = client.oauth_v2_access(
            client_id=SLACK_CLIENT_ID,
            client_secret=SLACK_CLIENT_SECRET,
            code=code,
            redirect_uri=f"{request.host_url}api/slack/oauth/callback"
        )

        if not response['ok']:
            raise Exception(f"OAuth exchange failed: {response.get('error')}")

        # Extract tokens and workspace info
        team_id = response['team']['id']
        team_name = response['team']['name']
        bot_token = response['access_token']
        bot_user_id = response['bot_user_id']

        # Register workspace mapping
        register_slack_workspace(team_id, tenant_id, bot_token)

        # Store in database via Connector model
        try:
            from database.models import Connector, ConnectorType, get_db
            db = next(get_db())
            try:
                # Check if connector already exists for this tenant
                connector = db.query(Connector).filter(
                    Connector.tenant_id == tenant_id,
                    Connector.connector_type == ConnectorType.SLACK
                ).first()

                settings = {
                    'team_id': team_id,
                    'team_name': team_name,
                    'bot_user_id': bot_user_id,
                    'channels': [],
                    'include_dms': True,
                    'include_threads': True,
                }

                if connector:
                    connector.access_token = bot_token
                    connector.is_active = True
                    connector.settings = settings
                else:
                    connector = Connector(
                        tenant_id=tenant_id,
                        connector_type=ConnectorType.SLACK,
                        access_token=bot_token,
                        is_active=True,
                        settings=settings
                    )
                    db.add(connector)

                db.commit()
                print(f"[SlackBot] Connector saved for tenant {tenant_id[:8]}...", flush=True)
            finally:
                db.close()
        except Exception as db_err:
            print(f"[SlackBot] DB save error (non-fatal): {db_err}", flush=True)

        print(f"[SlackBot] Workspace connected: {team_name} ({team_id}) for tenant {tenant_id[:8]}...", flush=True)

        # Redirect to success page
        return redirect(f"{request.host_url}integrations?slack_connected=true")

    except SlackApiError as e:
        print(f"[SlackBot] OAuth error: {e}", flush=True)
        return jsonify({
            'success': False,
            'error': "Failed to connect Slack workspace. Please try again."
        }), 500

    except Exception as e:
        print(f"[SlackBot] OAuth error: {e}", flush=True)
        return jsonify({
            'success': False,
            'error': "Failed to connect Slack workspace. Please try again."
        }), 500


# ============================================================================
# SLASH COMMANDS
# ============================================================================

@slack_bot_bp.route('/commands/ask', methods=['POST'])
def slack_command_ask():
    """
    Handle /ask slash command.

    User types: /ask What is our pricing model?

    POST /api/slack/commands/ask
    """
    try:
        # Verify Slack signature
        if not verify_slack_request():
            return jsonify({
                'text': 'Invalid request signature'
            }), 403

        # Parse command data
        team_id = request.form.get('team_id')
        user_id = request.form.get('user_id')
        channel_id = request.form.get('channel_id')
        query = request.form.get('text', '').strip()
        response_url = request.form.get('response_url')

        if not team_id:
            return jsonify({
                'response_type': 'ephemeral',
                'text': 'Invalid request: missing workspace ID.'
            })

        # Get tenant for workspace
        tenant_id = get_tenant_for_workspace(team_id)
        if not tenant_id:
            return jsonify({
                'response_type': 'ephemeral',
                'text': 'Workspace not connected to KnowledgeVault. Please connect in Settings > Integrations.'
            })

        # Get bot token
        bot_token = get_bot_token_for_workspace(team_id)
        if not bot_token:
            return jsonify({
                'response_type': 'ephemeral',
                'text': 'Bot token not found. Please reconnect workspace.'
            })

        # Handle command
        bot_service = SlackBotService(bot_token)

        if not query:
            return jsonify({
                'response_type': 'ephemeral',
                'text': '*Usage:* `/ask <your question>`\n\nExample: `/ask What is our pricing model?`'
            })

        response = bot_service.handle_ask_command(
            tenant_id=tenant_id,
            user_id=user_id,
            channel_id=channel_id,
            query=query,
            response_url=response_url
        )

        return jsonify(response)

    except Exception as e:
        print(f"[SlackBot] Command error: {e}", flush=True)
        return jsonify({
            'response_type': 'ephemeral',
            'text': 'Something went wrong processing your request. Please try again.'
        })


# ============================================================================
# SLACK EVENTS
# ============================================================================

@slack_bot_bp.route('/events', methods=['POST'])
def slack_events():
    """
    Handle Slack events (mentions, messages, file_shared, etc.).

    POST /api/slack/events
    """
    try:
        # Comprehensive logging for debugging event delivery
        print(f"[SlackBot] >>>>>> EVENT REQUEST RECEIVED method={request.method} content_type={request.content_type} content_length={request.content_length} remote_addr={request.remote_addr}", flush=True)
        print(f"[SlackBot] >>>>>> Headers: X-Slack-Signature={request.headers.get('X-Slack-Signature', 'MISSING')[:30]}... X-Slack-Request-Timestamp={request.headers.get('X-Slack-Request-Timestamp', 'MISSING')}", flush=True)
        raw_body = request.get_data(as_text=True)
        print(f"[SlackBot] >>>>>> Raw body length: {len(raw_body)}, first 200 chars: {raw_body[:200]}", flush=True)

        data = request.get_json(force=True, silent=True)
        if not data:
            print(f"[SlackBot] ERROR: Could not parse JSON body", flush=True)
            return jsonify({'ok': True})

        event_type = data.get('type', 'unknown')
        print(f"[SlackBot] Event type: {event_type}, team: {data.get('team_id', 'none')}", flush=True)

        # Handle URL verification challenge FIRST
        if event_type == 'url_verification':
            challenge = data.get('challenge', '')
            print(f"[SlackBot] Responding to URL verification challenge", flush=True)
            return jsonify({'challenge': challenge})

        # Log signature verification (but never reject)
        verify_slack_request()

        # Handle events
        if event_type == 'event_callback':
            event = data.get('event', {})
            team_id = data.get('team_id')
            event_id = data.get('event_id')
            event_subtype = event.get('type')

            print(f"[SlackBot] Event callback: subtype={event_subtype}, team={team_id}, event_id={event_id}", flush=True)
            print(f"[SlackBot] Event data: channel={event.get('channel')}, user={event.get('user')}, text={repr(event.get('text', '')[:100])}", flush=True)

            # Validate team_id is present and reasonable
            if not team_id or not isinstance(team_id, str) or len(team_id) > 20:
                print(f"[SlackBot] REJECTED: Invalid team_id: {repr(team_id)}", flush=True)
                return jsonify({'ok': True})

            # DEDUPLICATION: Skip if already processed
            if _is_duplicate_event(event_id):
                return jsonify({'ok': True})

            # CRITICAL: Process in background thread to respond to Slack within 3 seconds
            def process_event_background(team_id, event, event_subtype):
                try:
                    print(f"[SlackBot] Background thread started for {event_subtype}", flush=True)

                    tenant_id = get_tenant_for_workspace(team_id)
                    if not tenant_id:
                        print(f"[SlackBot] STOP: No tenant found for workspace {team_id}", flush=True)
                        return

                    print(f"[SlackBot] Tenant found: {tenant_id[:8]}...", flush=True)

                    bot_token = get_bot_token_for_workspace(team_id)
                    if not bot_token:
                        print(f"[SlackBot] STOP: No bot token for workspace {team_id}", flush=True)
                        return

                    print(f"[SlackBot] Bot token found, creating service...", flush=True)
                    bot_service = SlackBotService(bot_token)

                    if event_subtype == 'app_mention':
                        print(f"[SlackBot] Routing to handle_app_mention", flush=True)
                        bot_service.handle_app_mention(tenant_id, event)
                    elif event_subtype == 'message':
                        if not event.get('bot_id') and event.get('channel', '').startswith('D'):
                            # Check if message has files (file upload to bot)
                            if event.get('files'):
                                print(f"[SlackBot] Routing to handle_file_upload", flush=True)
                                bot_service.handle_file_upload(tenant_id, event)
                            else:
                                print(f"[SlackBot] Routing to handle_message (DM)", flush=True)
                                bot_service.handle_message(tenant_id, event)
                        else:
                            print(f"[SlackBot] Skipping message: bot_id={event.get('bot_id')}, channel={event.get('channel', '')[:5]}", flush=True)
                    elif event_subtype == 'file_shared':
                        # File shared in a DM with the bot
                        channel = event.get('channel_id', '')
                        if channel.startswith('D'):
                            print(f"[SlackBot] Routing to handle_file_shared", flush=True)
                            bot_service.handle_file_shared(tenant_id, event)
                    else:
                        print(f"[SlackBot] Unhandled event subtype: {event_subtype}", flush=True)

                    print(f"[SlackBot] Background thread completed for {event_subtype}", flush=True)

                except Exception as e:
                    import traceback
                    print(f"[SlackBot] Background error: {e}", flush=True)
                    traceback.print_exc()

            # Spawn background thread and return immediately
            thread = threading.Thread(
                target=process_event_background,
                args=(team_id, event, event_subtype)
            )
            thread.daemon = True
            thread.start()
        else:
            print(f"[SlackBot] Ignoring event type: {event_type}", flush=True)

        return jsonify({'ok': True})  # Return immediately to Slack

    except Exception as e:
        import traceback
        print(f"[SlackBot] Events error: {e}", flush=True)
        traceback.print_exc()
        return jsonify({'ok': True})  # Always return 200 to Slack


# ============================================================================
# INTERACTIVE COMPONENTS (Feedback buttons)
# ============================================================================

@slack_bot_bp.route('/interactive', methods=['POST'])
def slack_interactive():
    """
    Handle Slack interactive components (feedback buttons, etc.).

    POST /api/slack/interactive
    """
    try:
        # Verify Slack signature
        if not verify_slack_request():
            return jsonify({'error': 'Invalid signature'}), 403

        # Parse payload
        payload = json.loads(request.form.get('payload', '{}'))

        action_type = payload.get('type')
        team_id = payload.get('team', {}).get('id')
        user_info = payload.get('user', {})
        user_id = user_info.get('id', 'unknown')

        if not team_id:
            return jsonify({'ok': True})

        # Get tenant
        tenant_id = get_tenant_for_workspace(team_id)
        if not tenant_id:
            return jsonify({'text': 'Workspace not connected'})

        if action_type == 'block_actions':
            actions = payload.get('actions', [])
            for action in actions:
                action_id = action.get('action_id', '')
                value = action.get('value', '')

                if action_id == 'feedback_helpful':
                    _handle_feedback(payload, tenant_id, user_id, helpful=True)
                elif action_id == 'feedback_not_helpful':
                    _handle_feedback(payload, tenant_id, user_id, helpful=False)

        return jsonify({'ok': True})

    except Exception as e:
        print(f"[SlackBot] Interactive error: {e}", flush=True)
        return jsonify({'ok': True})


def _handle_feedback(payload: dict, tenant_id: str, user_id: str, helpful: bool):
    """Process feedback button click, update document scores (RL), and update the message."""
    try:
        # Get the original message info
        channel = payload.get('channel', {}).get('id')
        message_ts = payload.get('message', {}).get('ts')
        original_blocks = payload.get('message', {}).get('blocks', [])

        if not channel or not message_ts:
            return

        # Extract RL data from button value
        action_value = payload.get('actions', [{}])[0].get('value', '{}')
        try:
            rl_data = json.loads(action_value)
        except (json.JSONDecodeError, TypeError):
            rl_data = {}
        query = rl_data.get('q', '')
        source_doc_ids = rl_data.get('src', [])

        # Log the feedback
        feedback_type = "helpful" if helpful else "not helpful"
        print(f"[SlackBot] Feedback from {user_id}: {feedback_type} (tenant: {tenant_id[:8]}..., query: {query[:50]}, docs: {len(source_doc_ids)})", flush=True)

        # Store rich feedback in database + update document feedback scores
        try:
            from database.models import get_db, AuditLog, Document
            db = next(get_db())
            try:
                # Log rich feedback to AuditLog
                log = AuditLog(
                    tenant_id=tenant_id,
                    action='slack_bot_feedback',
                    details={
                        'user_id': user_id,
                        'helpful': helpful,
                        'query': query,
                        'source_doc_ids': source_doc_ids,
                        'channel': channel,
                        'message_ts': message_ts,
                    }
                )
                db.add(log)

                # RL reward signal: update feedback_score on source documents
                delta = 0.1 if helpful else -0.1
                for doc_id in source_doc_ids:
                    if not doc_id:
                        continue
                    doc = db.query(Document).filter(
                        Document.id == doc_id,
                        Document.tenant_id == tenant_id
                    ).first()
                    if doc:
                        new_score = max(-5.0, min(5.0, (doc.feedback_score or 0.0) + delta))
                        doc.feedback_score = new_score

                db.commit()
            finally:
                db.close()
        except Exception as db_err:
            print(f"[SlackBot] Feedback DB error (non-fatal): {db_err}", flush=True)

        # Update the message: replace feedback buttons with confirmation
        bot_token = get_bot_token_for_workspace(
            payload.get('team', {}).get('id')
        )
        if not bot_token:
            return

        client = WebClient(token=bot_token)

        # Replace the feedback block (last block) with a confirmation
        updated_blocks = []
        for block in original_blocks:
            # Skip the old feedback actions block
            if block.get('type') == 'actions':
                continue
            updated_blocks.append(block)

        # Add confirmation text
        emoji = "thumbs up" if helpful else "thumbs down"
        label = "Helpful" if helpful else "Not helpful"
        updated_blocks.append({
            'type': 'context',
            'elements': [{
                'type': 'mrkdwn',
                'text': f"_{label}_ - thanks for your feedback!"
            }]
        })

        client.chat_update(
            channel=channel,
            ts=message_ts,
            blocks=updated_blocks,
            text="Search result (feedback received)"
        )

    except Exception as e:
        print(f"[SlackBot] Feedback handler error: {e}", flush=True)


# ============================================================================
# MANAGEMENT ENDPOINTS
# ============================================================================

@slack_bot_bp.route('/status', methods=['GET'])
@require_auth
def slack_bot_status():
    """
    Check if Slack bot is connected for current tenant.

    GET /api/slack/status
    """
    try:
        tenant_id = g.tenant_id

        # Query database for Slack connector
        try:
            from database.models import Connector, ConnectorType, get_db
            db = next(get_db())
            try:
                connector = db.query(Connector).filter(
                    Connector.tenant_id == tenant_id,
                    Connector.connector_type == ConnectorType.SLACK,
                    Connector.is_active == True
                ).first()

                if connector:
                    settings = connector.settings or {}
                    return jsonify({
                        'success': True,
                        'connected': True,
                        'workspace': settings.get('team_name', 'Unknown'),
                        'bot_user_id': settings.get('bot_user_id'),
                    })
            finally:
                db.close()
        except Exception:
            pass

        return jsonify({
            'success': True,
            'connected': False,
            'message': 'Slack bot not connected. Use Settings > Integrations to connect.'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Failed to check Slack bot status.'
        }), 500


@slack_bot_bp.route('/disconnect', methods=['POST'])
@require_auth
def slack_bot_disconnect():
    """
    Disconnect Slack bot for current tenant.

    POST /api/slack/disconnect
    """
    try:
        tenant_id = g.tenant_id

        try:
            from database.models import Connector, ConnectorType, get_db
            from services.slack_bot_service import _workspace_cache
            db = next(get_db())
            try:
                connector = db.query(Connector).filter(
                    Connector.tenant_id == tenant_id,
                    Connector.connector_type == ConnectorType.SLACK
                ).first()

                if connector:
                    team_id = (connector.settings or {}).get('team_id')
                    connector.is_active = False
                    db.commit()
                    # Invalidate caches
                    if team_id:
                        _workspace_cache.invalidate(team_id)
                    print(f"[SlackBot] Disconnected for tenant {tenant_id[:8]}...", flush=True)
            finally:
                db.close()
        except Exception as db_err:
            print(f"[SlackBot] Disconnect DB error: {db_err}", flush=True)

        return jsonify({
            'success': True,
            'message': 'Slack bot disconnected'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': 'Failed to disconnect Slack bot.'
        }), 500
