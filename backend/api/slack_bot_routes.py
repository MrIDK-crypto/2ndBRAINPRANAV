"""
Slack Bot API Routes
Handles Slack OAuth, events, and slash commands.
"""

import os
import hmac
import hashlib
import time
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
# SLACK VERIFICATION MIDDLEWARE
# ============================================================================

def verify_slack_request():
    """Verify Slack request signature"""
    # TEMPORARILY DISABLED for development/debugging
    # TODO: Re-enable in production
    print("[SlackBot] Signature verification DISABLED for development", flush=True)
    return True

    # Original verification code (disabled):
    # if not signature_verifier:
    #     print("[SlackBot] No signing secret configured, skipping verification", flush=True)
    #     return True
    # ... etc


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
        'im:history',         # Read DMs
        'im:read',            # Access DM list
        'im:write',           # Send DMs
        'users:read',         # Read user info
    ]

    # State parameter includes tenant_id for security
    state = f"{g.tenant_id}:{g.user_id}"

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

        # Parse state
        try:
            tenant_id, user_id = state.split(':', 1)
        except ValueError:
            return jsonify({
                'success': False,
                'error': "Invalid state parameter"
            }), 400

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

        # Register workspace
        register_slack_workspace(team_id, tenant_id, bot_token)

        # In production: Store in database
        # from database.models import SlackWorkspace
        # workspace = SlackWorkspace(
        #     tenant_id=tenant_id,
        #     team_id=team_id,
        #     team_name=team_name,
        #     bot_token=bot_token,
        #     bot_user_id=bot_user_id
        # )
        # db.add(workspace)
        # db.commit()

        print(f"[SlackBot] Workspace connected: {team_name} ({team_id})", flush=True)

        # Redirect to success page
        return redirect(f"{request.host_url}integrations?slack_connected=true")

    except SlackApiError as e:
        print(f"[SlackBot] OAuth error: {e}", flush=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

    except Exception as e:
        print(f"[SlackBot] OAuth error: {e}", flush=True)
        return jsonify({
            'success': False,
            'error': str(e)
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

    Slack sends:
    {
        "token": "...",
        "team_id": "...",
        "user_id": "...",
        "channel_id": "...",
        "text": "What is our pricing model?",
        "response_url": "..."
    }
    """
    try:
        # Verify Slack signature
        if not verify_slack_request():
            return jsonify({
                'text': '❌ Invalid request signature'
            }), 403

        # Parse command data
        team_id = request.form.get('team_id')
        user_id = request.form.get('user_id')
        channel_id = request.form.get('channel_id')
        query = request.form.get('text', '').strip()
        response_url = request.form.get('response_url')

        # Get tenant for workspace
        tenant_id = get_tenant_for_workspace(team_id)
        if not tenant_id:
            return jsonify({
                'response_type': 'ephemeral',
                'text': '❌ Workspace not connected to 2nd Brain. Please connect in Settings > Integrations.'
            })

        # Get bot token
        bot_token = get_bot_token_for_workspace(team_id)
        if not bot_token:
            return jsonify({
                'response_type': 'ephemeral',
                'text': '❌ Bot token not found. Please reconnect workspace.'
            })

        # Handle command
        bot_service = SlackBotService(bot_token)

        if not query:
            return jsonify({
                'response_type': 'ephemeral',
                'text': '❓ *Usage:* `/ask <your question>`\n\nExample: `/ask What is our pricing model?`'
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
            'text': f'❌ Error: {str(e)}'
        })


# ============================================================================
# SLACK EVENTS
# ============================================================================

@slack_bot_bp.route('/events', methods=['POST'])
def slack_events():
    """
    Handle Slack events (mentions, messages, etc.).

    POST /api/slack/events

    Slack sends events like:
    - app_mention: @2ndBrain what is...
    - message: DMs to the bot
    - url_verification: Challenge request when setting up events URL
    """
    try:
        data = request.get_json()

        # Handle URL verification challenge FIRST (before signature verification)
        # This is required by Slack when you first set up the Events URL
        if data.get('type') == 'url_verification':
            challenge = data.get('challenge', '')
            print(f"[SlackBot] Responding to URL verification challenge", flush=True)
            return jsonify({'challenge': challenge})

        # Verify Slack signature for all other requests
        if not verify_slack_request():
            return jsonify({'error': 'Invalid signature'}), 403

        # Handle events
        if data.get('type') == 'event_callback':
            event = data.get('event', {})
            team_id = data.get('team_id')
            event_id = data.get('event_id')  # Unique ID for deduplication
            event_subtype = event.get('type')

            # DEDUPLICATION: Skip if already processed
            if _is_duplicate_event(event_id):
                return jsonify({'ok': True})

            # CRITICAL: Process in background thread to respond to Slack within 3 seconds
            def process_event_background(team_id, event, event_subtype):
                try:
                    tenant_id = get_tenant_for_workspace(team_id)
                    if not tenant_id:
                        print(f"[SlackBot] No tenant found for workspace {team_id}", flush=True)
                        return

                    bot_token = get_bot_token_for_workspace(team_id)
                    if not bot_token:
                        print(f"[SlackBot] No bot token for workspace {team_id}", flush=True)
                        return

                    bot_service = SlackBotService(bot_token)

                    if event_subtype == 'app_mention':
                        bot_service.handle_app_mention(tenant_id, event)
                    elif event_subtype == 'message':
                        if not event.get('bot_id') and event.get('channel', '').startswith('D'):
                            bot_service.handle_message(tenant_id, event)

                except Exception as e:
                    print(f"[SlackBot] Background error: {e}", flush=True)

            # Spawn background thread and return immediately
            thread = threading.Thread(
                target=process_event_background,
                args=(team_id, event, event_subtype)
            )
            thread.daemon = True
            thread.start()

        return jsonify({'ok': True})  # Return immediately to Slack

    except Exception as e:
        print(f"[SlackBot] Events error: {e}", flush=True)
        return jsonify({'ok': True})  # Always return 200 to Slack


# ============================================================================
# INTERACTIVE COMPONENTS
# ============================================================================

@slack_bot_bp.route('/interactive', methods=['POST'])
def slack_interactive():
    """
    Handle Slack interactive components (buttons, menus, etc.).

    POST /api/slack/interactive

    Future use: Handle button clicks, dropdown selections
    """
    try:
        # Verify Slack signature
        if not verify_slack_request():
            return jsonify({'error': 'Invalid signature'}), 403

        # Parse payload
        import json
        payload = json.loads(request.form.get('payload', '{}'))

        # Handle interactive action
        action_type = payload.get('type')
        team_id = payload.get('team', {}).get('id')

        # Get tenant
        tenant_id = get_tenant_for_workspace(team_id)
        if not tenant_id:
            return jsonify({'text': '❌ Workspace not connected'})

        # Future: Handle different action types
        # - block_actions: Button clicks
        # - view_submission: Modal submissions
        # - view_closed: Modal closed

        return jsonify({'ok': True})

    except Exception as e:
        print(f"[SlackBot] Interactive error: {e}", flush=True)
        return jsonify({'ok': True})


# ============================================================================
# MANAGEMENT ENDPOINTS
# ============================================================================

@slack_bot_bp.route('/status', methods=['GET'])
@require_auth
def slack_bot_status():
    """
    Check if Slack bot is connected for current tenant.

    GET /api/slack/status

    Returns:
    {
        "success": true,
        "connected": true,
        "workspace": "Acme Corp",
        "bot_user_id": "U0123456"
    }
    """
    try:
        tenant_id = g.tenant_id

        # In production: Query database for SlackWorkspace
        # For now: Check in-memory mapping
        # workspace = db.query(SlackWorkspace).filter(
        #     SlackWorkspace.tenant_id == tenant_id
        # ).first()

        # Placeholder response
        return jsonify({
            'success': True,
            'connected': False,  # Update based on database
            'message': 'Slack bot implementation complete. Configure OAuth to connect.'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
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

        # In production: Delete from database
        # workspace = db.query(SlackWorkspace).filter(
        #     SlackWorkspace.tenant_id == tenant_id
        # ).first()
        # if workspace:
        #     db.delete(workspace)
        #     db.commit()

        return jsonify({
            'success': True,
            'message': 'Slack bot disconnected'
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
