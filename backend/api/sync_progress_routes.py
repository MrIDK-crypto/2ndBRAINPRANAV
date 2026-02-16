"""
Sync Progress API Routes
Server-Sent Events (SSE) endpoint for real-time sync progress updates.
Uses standard library queue for gevent compatibility.
"""

import json
import queue
from flask import Blueprint, Response, request, jsonify, g
from services.sync_progress_service import get_sync_progress_service
from services.auth_service import require_auth

sync_progress_bp = Blueprint('sync_progress', __name__, url_prefix='/api/sync-progress')

# CORS allowed origins
ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://localhost:3006',
    'https://twondbrain-frontend.onrender.com',
    'https://2ndbrain.onrender.com',
    'https://twondbrain-frontend-docker.onrender.com',
    'https://secondbrain-frontend.onrender.com',
    'https://use2ndbrain.com',
    'https://api.use2ndbrain.com',
    'https://www.use2ndbrain.com'
]


@sync_progress_bp.route('/<sync_id>/stream', methods=['GET', 'OPTIONS'])
def stream_progress(sync_id: str):
    """
    Server-Sent Events endpoint for real-time sync progress.

    GET /api/sync-progress/<sync_id>/stream?token=<jwt_token>

    Note: EventSource cannot send custom headers, so token is passed as query param

    Returns:
        SSE stream with progress events:
        - started: Sync has begun
        - progress: Progress updated
        - complete: Sync finished successfully
        - error: Sync failed
    """
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        origin = request.headers.get('Origin', '')
        cors_origin = origin if origin in ALLOWED_ORIGINS else ALLOWED_ORIGINS[2]
        return Response('', status=200, headers={
            'Access-Control-Allow-Origin': cors_origin,
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            'Access-Control-Allow-Credentials': 'true',
            'Access-Control-Max-Age': '86400'
        })

    # Manual auth check for SSE (query param instead of header)
    from services.auth_service import JWTUtils

    print(f"[SSE] Stream request for sync_id: {sync_id}")

    token = request.args.get('token')
    if not token:
        print(f"[SSE] ERROR: No token provided in query params")
        return jsonify({"error": "Missing authorization token. Token must be passed as query parameter."}), 401

    payload, error = JWTUtils.decode_access_token(token)
    if error:
        print(f"[SSE] ERROR: Token validation failed: {error}")
        return jsonify({"error": f"Invalid token: {error}"}), 401

    # Store user info in Flask g object
    g.user_id = payload.get("sub")
    g.tenant_id = payload.get("tenant_id")
    g.email = payload.get("email")
    g.role = payload.get("role")

    print(f"[SSE] Authenticated user: {g.email} (tenant: {g.tenant_id})", flush=True)

    service = get_sync_progress_service()

    # Capture values needed inside generator BEFORE entering it
    # Flask's g object and app context are NOT available inside streaming generators
    from flask import current_app
    app = current_app._get_current_object()
    tenant_id = g.tenant_id

    def generate_events():
        """Generator for SSE events (gevent-compatible, no asyncio)"""
        print(f"[SSE] Starting event generator for {sync_id}")

        # Send immediate connection confirmation
        yield f"event: connected\n"
        yield f"data: {json.dumps({'sync_id': sync_id, 'status': 'connected'})}\n\n"

        # Create event queue (synchronous, gevent-compatible)
        try:
            event_queue = service.subscribe(sync_id)
            print(f"[SSE] Subscribed to sync {sync_id}")
        except Exception as e:
            print(f"[SSE] ERROR: Failed to subscribe: {e}")
            yield f"event: error\n"
            yield f"data: {json.dumps({'error': f'Failed to subscribe to sync: {str(e)}'})}\n\n"
            return

        # Send current state immediately so frontend has data
        try:
            current_state = service.get_progress(sync_id)
            if current_state:
                # current_state is already a dict
                print(f"[SSE] Sending current state: {current_state.get('status', 'unknown')}")
                yield f"event: current_state\n"
                yield f"data: {json.dumps(current_state)}\n\n"
            else:
                # Multi-worker fallback: Look up progress from database
                # Must use app.app_context() since generators run outside Flask request context
                print(f"[SSE] No in-memory state for {sync_id}, checking database...")
                from database.models import SessionLocal, Connector, ConnectorStatus
                db_state = None
                try:
                    with app.app_context():
                        db = SessionLocal()
                        try:
                            # Find connector with this sync_id - try multiple query approaches
                            connector = None

                            # First try: JSONB query (PostgreSQL)
                            try:
                                connector = db.query(Connector).filter(
                                    Connector.settings.op('->>')('current_sync_id') == sync_id
                                ).first()
                            except Exception as e:
                                print(f"[SSE] JSONB query failed: {e}")

                            # Fallback: Check all syncing connectors for this tenant
                            if not connector:
                                print(f"[SSE] Trying fallback: checking SYNCING connectors for tenant {tenant_id}")
                                syncing_connectors = db.query(Connector).filter(
                                    Connector.tenant_id == tenant_id,
                                    Connector.status == ConnectorStatus.SYNCING
                                ).all()

                                for c in syncing_connectors:
                                    settings = c.settings or {}
                                    if settings.get('current_sync_id') == sync_id:
                                        connector = c
                                        print(f"[SSE] Found via fallback: connector {c.id}")
                                        break

                            if connector:
                                print(f"[SSE] Found connector in DB for sync_id {sync_id}")
                                # Get sync progress from connector settings
                                settings = connector.settings or {}
                                sync_prog = settings.get("sync_progress", {})

                                # Construct progress from connector state + sync_progress
                                total_items = sync_prog.get("total_items", connector.last_sync_items_count or 0)
                                processed_items = sync_prog.get("processed_items", 0)
                                status = sync_prog.get("status", "syncing" if connector.status and connector.status.value == "syncing" else "connecting")
                                stage = sync_prog.get("stage", "Syncing..." if connector.status and connector.status.value == "syncing" else "Connecting to service...")

                                db_state = {
                                    "sync_id": sync_id,
                                    "tenant_id": str(connector.tenant_id),
                                    "user_id": str(connector.user_id),
                                    "connector_type": connector.connector_type.value if hasattr(connector.connector_type, 'value') else str(connector.connector_type),
                                    "status": status,
                                    "stage": stage,
                                    "total_items": total_items,
                                    "processed_items": processed_items,
                                    "failed_items": sync_prog.get("failed_items", 0),
                                    "current_item": sync_prog.get("current_item"),
                                    "error_message": connector.error_message,
                                    "percent_complete": (processed_items / total_items * 100) if total_items > 0 else 0
                                }
                            else:
                                print(f"[SSE] No connector found in DB for sync_id {sync_id}")
                        finally:
                            db.close()
                except Exception as db_err:
                    print(f"[SSE] DB lookup error: {db_err}", flush=True)
                    import traceback
                    traceback.print_exc()

                if db_state:
                    print(f"[SSE] Sending DB-based state: {db_state.get('status', 'unknown')}")
                    yield f"event: current_state\n"
                    yield f"data: {json.dumps(db_state)}\n\n"
                else:
                    print(f"[SSE] No current state found for {sync_id}")
        except Exception as e:
            print(f"[SSE] ERROR getting current state: {e}")
            import traceback
            traceback.print_exc()

        try:
            # Keep-alive timeout
            timeout = 30  # seconds

            while True:
                try:
                    # Wait for next event with timeout (synchronous, gevent-compatible)
                    event = event_queue.get(timeout=timeout)

                    print(f"[SSE] Sending event: {event['event']} for {sync_id}")

                    # Send event to client
                    yield f"event: {event['event']}\n"
                    yield f"data: {json.dumps(event['data'])}\n\n"

                    # Stop after complete or error
                    if event['event'] in ['complete', 'error']:
                        print(f"[SSE] Sync {sync_id} finished, closing stream")
                        break

                except queue.Empty:
                    # Send keep-alive comment
                    yield ": keep-alive\n\n"

        except Exception as e:
            print(f"[SSE] ERROR in event stream: {e}")
            import traceback
            traceback.print_exc()
            yield f"event: error\n"
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

        finally:
            # Clean up
            print(f"[SSE] Cleaning up subscription for {sync_id}")
            service.unsubscribe(sync_id, event_queue)

    # Get origin for CORS
    origin = request.headers.get('Origin', '')

    # Set CORS origin header if origin is allowed
    cors_origin = origin if origin in ALLOWED_ORIGINS else ALLOWED_ORIGINS[2]  # Default to production

    return Response(
        generate_events(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',  # Disable nginx buffering
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': cors_origin,
            'Access-Control-Allow-Credentials': 'true',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization'
        }
    )


@sync_progress_bp.route('/<sync_id>', methods=['GET'])
@require_auth
def get_progress(sync_id: str):
    """
    Get current progress state for a sync.

    GET /api/sync-progress/<sync_id>

    Returns:
        {
            "success": true,
            "progress": {
                "sync_id": "...",
                "status": "syncing",
                "stage": "Fetching emails...",
                "total_items": 100,
                "processed_items": 45,
                "failed_items": 2,
                "current_item": "Email from John",
                "percent_complete": 45.0,
                ...
            }
        }
    """
    service = get_sync_progress_service()
    progress = service.get_progress(sync_id)

    if progress:
        return jsonify({
            "success": True,
            "progress": progress
        })
    else:
        return jsonify({
            "success": False,
            "error": "Sync not found"
        }), 404


@sync_progress_bp.route('/<sync_id>/subscribe-email', methods=['POST', 'OPTIONS'])
@require_auth
def subscribe_email(sync_id: str):
    """
    Subscribe for email notification when sync completes.
    Called when user checks "Email me when done" checkbox.
    The email is sent server-side when sync completes, even if browser is closed.

    Persists to BOTH in-memory service AND database (Connector.settings)
    so it survives race conditions and multi-worker deployments.

    POST /api/sync-progress/<sync_id>/subscribe-email

    Returns:
        { "success": true, "message": "Email notification subscribed" }
    """
    from database.models import SessionLocal, User, Connector
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == g.user_id).first()
        if not user or not user.email:
            return jsonify({"success": False, "error": "User email not found"}), 400

        email = user.email

        # 1) Try in-memory service (works if sync is on this worker)
        service = get_sync_progress_service()
        service.subscribe_email(sync_id, email)

        # 2) ALSO persist to database (survives multi-worker, race conditions)
        # Find connector with this sync_id
        connectors = db.query(Connector).filter(
            Connector.tenant_id == g.tenant_id
        ).all()

        db_persisted = False
        for connector in connectors:
            settings = connector.settings or {}
            if settings.get('current_sync_id') == sync_id:
                settings['notify_email'] = email
                connector.settings = settings
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(connector, 'settings')
                db.commit()
                db_persisted = True
                print(f"[SubscribeEmail] Persisted notify_email to DB for sync {sync_id}")
                break

        if not db_persisted:
            print(f"[SubscribeEmail] No connector found in DB for sync {sync_id}, in-memory only")

        return jsonify({
            "success": True,
            "message": f"Email notification will be sent to {email} when sync completes"
        })
    except Exception as e:
        print(f"[SubscribeEmail] Error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        db.close()


@sync_progress_bp.route('/<sync_id>/notify', methods=['POST', 'OPTIONS'])
@require_auth
def send_notification(sync_id: str):
    """
    Send email notification for sync completion.

    This endpoint is called by the frontend only when the user
    has explicitly enabled "Email me when done" option.

    POST /api/sync-progress/<sync_id>/notify

    Returns:
        {
            "success": true,
            "message": "Notification sent"
        }
    """
    from database.models import SessionLocal, User, Connector
    db = SessionLocal()

    try:
        # Get user email first
        user = db.query(User).filter(User.id == g.user_id).first()

        if not user or not user.email:
            return jsonify({
                "success": False,
                "error": "User email not found"
            }), 400

        # Try to get progress from in-memory service
        service = get_sync_progress_service()
        progress = service.get_progress(sync_id)

        # Fallback: Look up from database if not in memory (multi-worker deployment)
        if not progress:
            print(f"[Notify] No in-memory progress for {sync_id}, checking database...")
            connector = db.query(Connector).filter(
                Connector.tenant_id == g.tenant_id,
                Connector.settings.op('->>')('current_sync_id') == sync_id
            ).first()

            if connector:
                settings = connector.settings or {}
                sync_prog = settings.get('sync_progress', {})
                progress = {
                    'connector_type': connector.connector_type.value if hasattr(connector.connector_type, 'value') else str(connector.connector_type),
                    'total_items': sync_prog.get('total_items', connector.last_sync_items_count or 0),
                    'processed_items': sync_prog.get('processed_items', connector.last_sync_items_count or 0),
                    'failed_items': sync_prog.get('failed_items', 0),
                    'error_message': connector.error_message,
                    'started_at': None,
                    'completed_at': None
                }

        if not progress:
            # Still no progress? Use defaults based on connector type from request
            print(f"[Notify] Using default progress for notification")
            progress = {
                'connector_type': 'github',
                'total_items': 0,
                'processed_items': 0,
                'failed_items': 0,
                'error_message': None
            }

        # Get sync details from progress
        connector_type = progress.get('connector_type', 'integration')
        total_items = progress.get('total_items', 0)
        processed_items = progress.get('processed_items', 0)
        failed_items = progress.get('failed_items', 0)
        error_message = progress.get('error_message')

        # Calculate duration
        started_at_str = progress.get('started_at')
        completed_at_str = progress.get('completed_at')
        duration = 0

        if started_at_str and completed_at_str:
            try:
                from datetime import datetime
                started_at = datetime.fromisoformat(started_at_str.replace('Z', '+00:00'))
                completed_at = datetime.fromisoformat(completed_at_str.replace('Z', '+00:00'))
                duration = (completed_at - started_at).total_seconds()
            except (ValueError, AttributeError):
                pass

        # Send email notification
        from services.email_notification_service import get_email_service
        email_service = get_email_service()

        success = email_service.send_sync_complete_notification(
            user_email=user.email,
            connector_type=connector_type,
            total_items=total_items,
            processed_items=processed_items,
            failed_items=failed_items,
            duration_seconds=duration,
            error_message=error_message
        )

        if success:
            return jsonify({
                "success": True,
                "message": "Notification sent"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Failed to send notification"
            }), 500

    finally:
        db.close()


@sync_progress_bp.route('/test/start', methods=['POST'])
@require_auth
def start_test_sync():
    """
    Start a test sync for demo purposes.
    This simulates a sync without needing real OAuth.

    POST /api/sync-progress/test/start
    Body: { "connector_type": "github" }
    """
    import threading

    data = request.get_json() or {}
    connector_type = data.get('connector_type', 'github')

    service = get_sync_progress_service()
    sync_id = service.start_sync(
        tenant_id=g.tenant_id,
        user_id=g.user_id,
        connector_type=connector_type
    )

    # Simulate sync progress in background thread
    def simulate_sync():
        import gevent
        gevent.sleep(1)
        service.update_progress(sync_id, status='syncing', stage='Analyzing repository...', total_items=10)

        for i in range(1, 11):
            gevent.sleep(1)
            service.update_progress(
                sync_id,
                status='syncing',
                stage=f'Processing file {i}/10',
                processed_items=i,
                current_item=f'file_{i}.py'
            )

        gevent.sleep(1)
        service.update_progress(sync_id, status='complete', stage='Sync complete')

    thread = threading.Thread(target=simulate_sync, daemon=True)
    thread.start()

    return jsonify({
        "success": True,
        "sync_id": sync_id,
        "message": "Test sync started"
    })
