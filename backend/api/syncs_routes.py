"""
Syncs API Routes - Clean polling-based sync status endpoints.
These are the PRIMARY source of truth for frontend sync tracking.

GET /api/syncs/active      - All active + recently completed syncs for tenant
GET /api/syncs/<sync_id>   - Current state of a specific sync (poll-friendly)
"""

import json
from flask import Blueprint, request, jsonify, g
from services.sync_progress_service import get_sync_progress_service
from services.auth_service import require_auth

syncs_bp = Blueprint('syncs', __name__, url_prefix='/api/syncs')


@syncs_bp.route('/active', methods=['GET'])
@require_auth
def get_active_syncs():
    """
    Get all active and recently completed syncs for the current tenant.

    This endpoint is called by the frontend on app load to recover sync state
    after page refresh or navigation. It's the foundation of the "survive everything"
    architecture.

    Returns active syncs + syncs completed within the last 5 minutes.

    GET /api/syncs/active

    Response:
    {
        "success": true,
        "syncs": [
            {
                "sync_id": "uuid",
                "connector_type": "gmail",
                "status": "saving",
                "phase": "saving",
                "phase_number": 1,
                "total_phases": 3,
                "phase_label": "Saving documents",
                "phase_items_total": 150,
                "phase_items_done": 45,
                "overall_percent": 10.0,
                "current_item": "Email from John",
                "error_message": null,
                "started_at": "2026-02-16T...",
                "completed_at": null,
                "items_synced": 150
            }
        ]
    }
    """
    service = get_sync_progress_service()

    # 1. Get from in-memory service (fast, real-time)
    syncs = service.get_all_for_tenant(g.tenant_id, include_recent_completed=True)

    # 2. If no in-memory syncs, check database for any SYNCING connectors
    #    (handles server restart scenario where in-memory state was lost)
    if not syncs:
        try:
            from database.models import SessionLocal, Connector, ConnectorStatus
            db = SessionLocal()
            try:
                syncing = db.query(Connector).filter(
                    Connector.tenant_id == g.tenant_id,
                    Connector.status == ConnectorStatus.SYNCING,
                    Connector.is_active == True
                ).all()

                for c in syncing:
                    settings = c.settings or {}
                    sync_id = settings.get('current_sync_id')
                    sync_prog = settings.get('sync_progress', {})
                    if sync_id:
                        ct = c.connector_type.value if hasattr(c.connector_type, 'value') else str(c.connector_type)
                        syncs.append(_build_sync_response(
                            sync_id=sync_id,
                            connector_type=ct,
                            status=sync_prog.get('status', 'syncing'),
                            stage=sync_prog.get('stage', 'Syncing...'),
                            total_items=sync_prog.get('total_items', 0),
                            processed_items=sync_prog.get('processed_items', 0),
                            failed_items=sync_prog.get('failed_items', 0),
                            overall_percent=sync_prog.get('overall_percent', 0),
                            current_item=sync_prog.get('current_item'),
                            error_message=c.error_message,
                            started_at=settings.get('sync_started_at'),
                            completed_at=None
                        ))
            finally:
                db.close()
        except Exception as e:
            print(f"[Syncs] DB fallback error: {e}")

    # 3. Enrich each sync with phase info
    enriched = [_enrich_with_phase_info(s) for s in syncs]

    return jsonify({
        "success": True,
        "syncs": enriched
    })


@syncs_bp.route('/<sync_id>', methods=['GET'])
@require_auth
def get_sync(sync_id: str):
    """
    Get current state of a specific sync. This is the poll-friendly endpoint.
    Frontend polls this every 2 seconds during active syncs.

    GET /api/syncs/<sync_id>

    Response:
    {
        "success": true,
        "sync": { ... same shape as /active items ... }
    }
    """
    service = get_sync_progress_service()

    # 1. Try in-memory service (fast, real-time)
    progress = service.get_progress(sync_id)

    # 2. Fall back to database
    if not progress:
        try:
            from database.models import SessionLocal, Connector, ConnectorStatus
            db = SessionLocal()
            try:
                # Find connector with this sync_id
                syncing = db.query(Connector).filter(
                    Connector.tenant_id == g.tenant_id,
                    Connector.is_active == True
                ).all()

                for c in syncing:
                    settings = c.settings or {}
                    if settings.get('current_sync_id') == sync_id:
                        sync_prog = settings.get('sync_progress', {})
                        ct = c.connector_type.value if hasattr(c.connector_type, 'value') else str(c.connector_type)

                        # Determine status from connector state
                        if c.status == ConnectorStatus.SYNCING:
                            status = sync_prog.get('status', 'syncing')
                        elif c.status == ConnectorStatus.CONNECTED:
                            status = 'complete'
                        elif c.status == ConnectorStatus.ERROR:
                            status = 'error'
                        else:
                            status = sync_prog.get('status', 'connecting')

                        progress = _build_sync_response(
                            sync_id=sync_id,
                            connector_type=ct,
                            status=status,
                            stage=sync_prog.get('stage', 'Processing...'),
                            total_items=sync_prog.get('total_items', 0),
                            processed_items=sync_prog.get('processed_items', 0),
                            failed_items=sync_prog.get('failed_items', 0),
                            overall_percent=sync_prog.get('overall_percent', 0),
                            current_item=sync_prog.get('current_item'),
                            error_message=c.error_message if c.status == ConnectorStatus.ERROR else None,
                            started_at=settings.get('sync_started_at'),
                            completed_at=None if c.status == ConnectorStatus.SYNCING else (
                                c.last_sync_at.isoformat() if c.last_sync_at else None
                            )
                        )
                        break
            finally:
                db.close()
        except Exception as e:
            print(f"[Syncs] DB fallback error: {e}")

    if not progress:
        return jsonify({"success": False, "error": "Sync not found"}), 404

    enriched = _enrich_with_phase_info(progress)

    return jsonify({
        "success": True,
        "sync": enriched
    })


def _build_sync_response(**kwargs) -> dict:
    """Build a standardized sync response dict."""
    return {
        'sync_id': kwargs.get('sync_id'),
        'connector_type': kwargs.get('connector_type'),
        'status': kwargs.get('status', 'connecting'),
        'stage': kwargs.get('stage', 'Connecting...'),
        'total_items': kwargs.get('total_items', 0),
        'processed_items': kwargs.get('processed_items', 0),
        'failed_items': kwargs.get('failed_items', 0),
        'overall_percent': round(kwargs.get('overall_percent', 0), 1),
        'percent_complete': round(kwargs.get('overall_percent', 0), 1),
        'current_item': kwargs.get('current_item'),
        'error_message': kwargs.get('error_message'),
        'started_at': kwargs.get('started_at'),
        'completed_at': kwargs.get('completed_at'),
    }


def _enrich_with_phase_info(sync: dict) -> dict:
    """Add phase-aware fields to a sync response.

    The 3 phases are:
      1. Saving (0-33%):      Fetching + deduplicating + saving to DB
      2. Extracting (33-66%): AI-powered summary extraction
      3. Embedding (66-99%):  Vector embedding for RAG search

    Frontend uses these to show "Step X of 3: Phase name"
    """
    status = sync.get('status', 'connecting')
    pct = sync.get('overall_percent', 0)

    # Determine phase from status or percentage
    if status in ('connecting', 'fetching'):
        phase = 'fetching'
        phase_number = 0
        total_phases = 3
        phase_label = 'Connecting to service'
    elif status == 'saving' or (status == 'syncing' and pct <= 33):
        phase = 'saving'
        phase_number = 1
        total_phases = 3
        phase_label = 'Saving documents'
    elif status == 'extracting' or (33 < pct <= 66 and status not in ('embedding', 'complete', 'error')):
        phase = 'extracting'
        phase_number = 2
        total_phases = 3
        phase_label = 'Extracting summaries'
    elif status == 'embedding' or (66 < pct < 100 and status not in ('complete', 'error')):
        phase = 'embedding'
        phase_number = 3
        total_phases = 3
        phase_label = 'Embedding for search'
    elif status in ('complete', 'completed'):
        phase = 'complete'
        phase_number = 3
        total_phases = 3
        phase_label = 'Sync complete'
    elif status == 'error':
        phase = 'error'
        phase_number = 0
        total_phases = 3
        phase_label = 'Sync failed'
    else:
        phase = 'saving'
        phase_number = 1
        total_phases = 3
        phase_label = 'Processing'

    # Calculate phase-level progress (how far within the current phase)
    if phase == 'saving':
        phase_percent = min(pct / 33.0 * 100, 100) if pct <= 33 else 100
    elif phase == 'extracting':
        phase_percent = min((pct - 33) / 33.0 * 100, 100) if 33 < pct <= 66 else 100
    elif phase == 'embedding':
        phase_percent = min((pct - 66) / 33.0 * 100, 100) if 66 < pct < 100 else 100
    elif phase == 'complete':
        phase_percent = 100
    else:
        phase_percent = 0

    sync['phase'] = phase
    sync['phase_number'] = phase_number
    sync['total_phases'] = total_phases
    sync['phase_label'] = phase_label
    sync['phase_percent'] = round(phase_percent, 1)

    return sync
