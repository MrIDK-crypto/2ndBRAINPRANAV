"""
Slack Events Server - Dedicated server for handling Slack events

This is a minimal Flask server specifically for handling Slack events,
including the URL verification challenge required by Slack.

Deploy this separately on Render to handle Slack webhook events.
"""

import os
import hmac
import hashlib
import time
import requests
from flask import Flask, request, jsonify, redirect
from flask_cors import CORS

app = Flask(__name__)

# CORS configuration
CORS(app, supports_credentials=True)

# Slack credentials
SLACK_SIGNING_SECRET = os.getenv('SLACK_SIGNING_SECRET')
SLACK_CLIENT_ID = os.getenv('SLACK_CLIENT_ID')
SLACK_CLIENT_SECRET = os.getenv('SLACK_CLIENT_SECRET')
SLACK_BOT_TOKEN = os.getenv('SLACK_BOT_TOKEN')

# URLs
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')
BACKEND_URL = os.getenv('BACKEND_URL', 'http://localhost:5003')


def verify_slack_signature():
    """Verify that the request came from Slack"""
    if not SLACK_SIGNING_SECRET:
        print("[SlackEvents] Warning: No SLACK_SIGNING_SECRET set, skipping verification", flush=True)
        return True

    timestamp = request.headers.get('X-Slack-Request-Timestamp', '')
    signature = request.headers.get('X-Slack-Signature', '')

    # Check timestamp to prevent replay attacks (5 minute window)
    try:
        if abs(time.time() - int(timestamp)) > 60 * 5:
            print("[SlackEvents] Request timestamp too old", flush=True)
            return False
    except (ValueError, TypeError):
        print("[SlackEvents] Invalid timestamp", flush=True)
        return False

    # Create the signature base string
    body = request.get_data(as_text=True)
    sig_basestring = f"v0:{timestamp}:{body}"

    # Create HMAC SHA256 signature
    my_signature = 'v0=' + hmac.new(
        SLACK_SIGNING_SECRET.encode('utf-8'),
        sig_basestring.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    # Compare signatures
    if not hmac.compare_digest(my_signature, signature):
        print("[SlackEvents] Invalid signature", flush=True)
        return False

    return True


@app.route('/api/slack/events', methods=['POST'])
def slack_events():
    """
    Handle Slack events including URL verification challenge.

    Slack sends a challenge request when you first configure the Events URL.
    We must respond with the challenge value to verify ownership.
    """
    try:
        data = request.get_json()

        print(f"[SlackEvents] Received event type: {data.get('type')}", flush=True)

        # Handle URL verification challenge (MUST respond immediately)
        if data.get('type') == 'url_verification':
            challenge = data.get('challenge', '')
            print(f"[SlackEvents] Responding to challenge: {challenge[:20]}...", flush=True)
            return jsonify({'challenge': challenge})

        # Verify signature for all other requests
        if not verify_slack_signature():
            return jsonify({'error': 'Invalid signature'}), 403

        # Handle event callbacks
        if data.get('type') == 'event_callback':
            event = data.get('event', {})
            event_type = event.get('type')
            team_id = data.get('team_id')

            print(f"[SlackEvents] Event: {event_type} from team: {team_id}", flush=True)

            # Import services only when needed to avoid circular imports
            try:
                from services.slack_bot_service import (
                    SlackBotService,
                    get_tenant_for_workspace,
                    get_bot_token_for_workspace
                )

                # Get tenant for workspace
                tenant_id = get_tenant_for_workspace(team_id)
                if not tenant_id:
                    print(f"[SlackEvents] No tenant found for workspace {team_id}", flush=True)
                    return jsonify({'ok': True})

                # Get bot token
                bot_token = get_bot_token_for_workspace(team_id)
                if not bot_token:
                    print(f"[SlackEvents] No bot token for workspace {team_id}", flush=True)
                    return jsonify({'ok': True})

                bot_service = SlackBotService(bot_token)

                # Handle app_mention (@2ndBrain ...)
                if event_type == 'app_mention':
                    bot_service.handle_app_mention(tenant_id, event)

                # Handle direct messages
                elif event_type == 'message':
                    # Ignore bot messages and channel messages
                    if not event.get('bot_id') and event.get('channel', '').startswith('D'):
                        bot_service.handle_message(tenant_id, event)

            except ImportError as e:
                print(f"[SlackEvents] Service import error: {e}", flush=True)
            except Exception as e:
                print(f"[SlackEvents] Event handling error: {e}", flush=True)

        return jsonify({'ok': True})

    except Exception as e:
        print(f"[SlackEvents] Error: {e}", flush=True)
        # Always return 200 to Slack to prevent retries
        return jsonify({'ok': True})


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'slack-events-server',
        'timestamp': time.time()
    })


@app.route('/', methods=['GET'])
def root():
    """Root endpoint"""
    return jsonify({
        'service': '2nd Brain Slack Events Server',
        'status': 'running',
        'endpoints': {
            '/api/slack/events': 'Slack events webhook',
            '/api/integrations/slack/callback': 'Slack OAuth callback & events',
            '/api/slack/oauth/authorize': 'Start Slack OAuth',
            '/api/slack/oauth/callback': 'Slack OAuth callback',
            '/api/health': 'Health check'
        }
    })


# =============================================================================
# SLACK OAUTH ENDPOINTS
# =============================================================================

@app.route('/api/slack/oauth/authorize', methods=['GET'])
def slack_oauth_authorize():
    """Start Slack OAuth flow - redirects user to Slack authorization page"""
    if not SLACK_CLIENT_ID:
        return jsonify({'error': 'Slack client ID not configured'}), 500

    # Use the callback URL that matches what's configured in Slack app
    redirect_uri = f"{BACKEND_URL}/api/integrations/slack/callback"

    # Slack OAuth scopes needed for the bot
    scopes = [
        'channels:history',
        'channels:read',
        'chat:write',
        'files:read',
        'groups:history',
        'groups:read',
        'im:history',
        'im:read',
        'mpim:history',
        'mpim:read',
        'users:read',
        'app_mentions:read'
    ]

    slack_auth_url = (
        f"https://slack.com/oauth/v2/authorize"
        f"?client_id={SLACK_CLIENT_ID}"
        f"&scope={','.join(scopes)}"
        f"&redirect_uri={redirect_uri}"
    )

    print(f"[SlackOAuth] Redirecting to Slack authorization", flush=True)
    return redirect(slack_auth_url)


@app.route('/api/integrations/slack/callback', methods=['GET', 'POST'])
def slack_integrations_callback():
    """
    Handle both Slack OAuth callback (GET) and Events (POST).
    This is the main callback URL configured in Slack app settings.
    """

    # POST = Slack Events (including url_verification challenge)
    if request.method == 'POST':
        try:
            data = request.get_json()

            print(f"[SlackCallback] POST - Event type: {data.get('type')}", flush=True)

            # Handle URL verification challenge (MUST respond immediately)
            if data.get('type') == 'url_verification':
                challenge = data.get('challenge', '')
                print(f"[SlackCallback] Responding to challenge", flush=True)
                # Return challenge as plain text (Slack accepts both JSON and plain text)
                return challenge, 200, {'Content-Type': 'text/plain'}

            # Verify signature for all other requests
            if not verify_slack_signature():
                return jsonify({'error': 'Invalid signature'}), 403

            # Handle event callbacks (delegate to main events handler logic)
            if data.get('type') == 'event_callback':
                event = data.get('event', {})
                event_type = event.get('type')
                team_id = data.get('team_id')

                print(f"[SlackCallback] Event: {event_type} from team: {team_id}", flush=True)

                # Process event (same logic as /api/slack/events)
                try:
                    from services.slack_bot_service import (
                        SlackBotService,
                        get_tenant_for_workspace,
                        get_bot_token_for_workspace
                    )

                    tenant_id = get_tenant_for_workspace(team_id)
                    if tenant_id:
                        bot_token = get_bot_token_for_workspace(team_id)
                        if bot_token:
                            bot_service = SlackBotService(bot_token)

                            if event_type == 'app_mention':
                                bot_service.handle_app_mention(tenant_id, event)
                            elif event_type == 'message':
                                if not event.get('bot_id') and event.get('channel', '').startswith('D'):
                                    bot_service.handle_message(tenant_id, event)

                except ImportError as e:
                    print(f"[SlackCallback] Service import error: {e}", flush=True)
                except Exception as e:
                    print(f"[SlackCallback] Event handling error: {e}", flush=True)

            return jsonify({'ok': True})

        except Exception as e:
            print(f"[SlackCallback] POST Error: {e}", flush=True)
            return jsonify({'ok': True})

    # GET = OAuth callback
    code = request.args.get('code')
    error = request.args.get('error')

    print(f"[SlackOAuth] Callback received - code: {'yes' if code else 'no'}, error: {error}", flush=True)

    if error:
        print(f"[SlackOAuth] Error from Slack: {error}", flush=True)
        return redirect(f"{FRONTEND_URL}/integrations?error={error}")

    if not code:
        print("[SlackOAuth] No code provided", flush=True)
        return redirect(f"{FRONTEND_URL}/integrations?error=no_code")

    if not SLACK_CLIENT_ID or not SLACK_CLIENT_SECRET:
        print("[SlackOAuth] Missing client credentials", flush=True)
        return redirect(f"{FRONTEND_URL}/integrations?error=server_config")

    try:
        # Exchange code for access token
        redirect_uri = f"{BACKEND_URL}/api/integrations/slack/callback"

        response = requests.post(
            'https://slack.com/api/oauth.v2.access',
            data={
                'client_id': SLACK_CLIENT_ID,
                'client_secret': SLACK_CLIENT_SECRET,
                'code': code,
                'redirect_uri': redirect_uri
            }
        )

        data = response.json()
        print(f"[SlackOAuth] Token exchange response ok: {data.get('ok')}", flush=True)

        if not data.get('ok'):
            error_msg = data.get('error', 'unknown_error')
            print(f"[SlackOAuth] Token exchange failed: {error_msg}", flush=True)
            return redirect(f"{FRONTEND_URL}/integrations?error={error_msg}")

        # Extract tokens and workspace info
        access_token = data.get('access_token')
        team_id = data.get('team', {}).get('id')
        team_name = data.get('team', {}).get('name')
        bot_user_id = data.get('bot_user_id')

        print(f"[SlackOAuth] Success! Team: {team_name} ({team_id})", flush=True)

        # Store the token (you may want to save this to a database)
        # For now, we'll just redirect with success
        # In production, save: team_id, access_token, team_name, bot_user_id

        return redirect(f"{FRONTEND_URL}/integrations?slack=success&team={team_name}")

    except Exception as e:
        print(f"[SlackOAuth] Exception: {e}", flush=True)
        return redirect(f"{FRONTEND_URL}/integrations?error=server_error")


@app.route('/api/slack/oauth/callback', methods=['GET'])
def slack_oauth_callback():
    """Alternative OAuth callback URL - redirects to main callback"""
    # Just redirect to the main callback handler
    query_string = request.query_string.decode('utf-8')
    return redirect(f"/api/integrations/slack/callback?{query_string}")


if __name__ == '__main__':
    port = int(os.getenv('PORT', 5003))
    print(f"[SlackEvents] Starting server on port {port}", flush=True)
    print(f"[SlackEvents] SLACK_CLIENT_ID: {'Set' if SLACK_CLIENT_ID else 'Not set'}", flush=True)
    print(f"[SlackEvents] SLACK_SIGNING_SECRET: {'Set' if SLACK_SIGNING_SECRET else 'Not set'}", flush=True)
    print(f"[SlackEvents] BACKEND_URL: {BACKEND_URL}", flush=True)
    print(f"[SlackEvents] FRONTEND_URL: {FRONTEND_URL}", flush=True)
    app.run(host='0.0.0.0', port=port, debug=False)
