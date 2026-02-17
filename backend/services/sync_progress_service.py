"""
Sync Progress Tracking Service
Real-time progress tracking for integration syncs with SSE support.
Uses gevent-compatible queues for production deployment.

Phase-based progress:
  - connecting:  0%        (instant)
  - fetching:    0%        (indeterminate - duration unknown)
  - saving:      0% - 33%  (per-item accurate)
  - extracting: 33% - 66%  (per-item accurate)
  - embedding:  66% - 99%  (per-item accurate)
  - complete:   100%
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict
import uuid
import queue  # Standard library thread-safe queue (works with gevent)


@dataclass
class SyncProgress:
    """Progress state for a sync operation"""
    sync_id: str
    tenant_id: str
    user_id: str
    connector_type: str
    status: str  # 'connecting', 'fetching', 'saving', 'extracting', 'embedding', 'complete', 'error'
    stage: str  # Current stage description
    total_items: int
    processed_items: int
    failed_items: int
    overall_percent: float = 0.0  # Server-calculated 0-100, used by frontend directly
    current_item: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    notify_email: Optional[str] = None  # Email to notify on completion (server-side)

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        data = {
            'sync_id': self.sync_id,
            'tenant_id': self.tenant_id,
            'user_id': self.user_id,
            'connector_type': self.connector_type,
            'status': self.status,
            'stage': self.stage,
            'total_items': self.total_items,
            'processed_items': self.processed_items,
            'failed_items': self.failed_items,
            'overall_percent': round(self.overall_percent, 1),
            'percent_complete': round(self.overall_percent, 1),  # Alias for backward compat
            'current_item': self.current_item,
            'error_message': self.error_message,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }
        return data

    @property
    def percent_complete(self) -> float:
        """Return server-calculated overall percent"""
        return self.overall_percent


class SyncProgressService:
    """
    Service for tracking sync progress and emitting real-time updates via SSE.
    Uses standard library queue.Queue for gevent compatibility.

    Progress is phase-based:
      connecting → fetching → saving (0-33%) → extracting (33-66%) → embedding (66-99%) → complete (100%)

    The server calculates overall_percent accurately. The frontend uses it directly.
    """

    def __init__(self):
        # In-memory storage of sync progress
        self._progress: Dict[str, SyncProgress] = {}

        # Event queues for SSE subscribers (using thread-safe queue)
        self._subscribers: Dict[str, List[queue.Queue]] = defaultdict(list)

        # Track user email subscriptions for batch completion notification
        # Maps user_id -> email address (user wants email when ALL their syncs complete)
        self._user_email_subscriptions: Dict[str, str] = {}

        # Track which users have already received their batch email (prevents duplicates)
        self._email_sent_for_user: set = set()

        # Cleanup old syncs after this duration (seconds)
        self._cleanup_age = 3600  # 1 hour

        # Start periodic cleanup thread
        import threading
        self._cleanup_thread = threading.Thread(target=self._periodic_cleanup, daemon=True)
        self._cleanup_thread.start()

    def start_sync(
        self,
        tenant_id: str,
        user_id: str,
        connector_type: str
    ) -> str:
        """
        Start a new sync operation.

        Returns:
            sync_id: Unique identifier for this sync
        """
        sync_id = str(uuid.uuid4())

        # NOTE: Don't clear email_sent flag here - only clear when user explicitly subscribes
        # This prevents duplicate emails when user runs multiple syncs in sequence

        self._progress[sync_id] = SyncProgress(
            sync_id=sync_id,
            tenant_id=tenant_id,
            user_id=user_id,
            connector_type=connector_type,
            status='connecting',
            stage='Connecting to service...',
            total_items=0,
            processed_items=0,
            failed_items=0,
            overall_percent=0.0,
            started_at=datetime.now(timezone.utc)
        )

        self._emit_event(sync_id, 'started')

        print(f"[SyncProgress] Started sync: {sync_id} for {connector_type}")
        return sync_id

    def update_progress(
        self,
        sync_id: str,
        status: Optional[str] = None,
        stage: Optional[str] = None,
        total_items: Optional[int] = None,
        processed_items: Optional[int] = None,
        failed_items: Optional[int] = None,
        current_item: Optional[str] = None,
        error_message: Optional[str] = None,
        overall_percent: Optional[float] = None
    ):
        """Update sync progress with any combination of fields"""
        if sync_id not in self._progress:
            print(f"[SyncProgress] WARNING: sync_id {sync_id} not found")
            return

        progress = self._progress[sync_id]

        if status:
            progress.status = status
        if stage:
            progress.stage = stage
        if total_items is not None:
            progress.total_items = total_items
        if processed_items is not None:
            progress.processed_items = processed_items
        if failed_items is not None:
            progress.failed_items = failed_items
        if current_item is not None:
            progress.current_item = current_item
        if error_message is not None:
            progress.error_message = error_message
        if overall_percent is not None:
            progress.overall_percent = overall_percent

        # If status is complete or error, mark completion time
        if status in ('complete', 'completed', 'error'):
            progress.completed_at = datetime.now(timezone.utc)
            event_type = 'complete' if status in ('complete', 'completed') else 'error'
            self._emit_event(sync_id, event_type)
        else:
            self._emit_event(sync_id, 'progress')

    def increment_processed(
        self,
        sync_id: str,
        current_item: Optional[str] = None,
        failed: bool = False,
        overall_percent: Optional[float] = None
    ):
        """Increment processed item count with smart SSE emission"""
        if sync_id not in self._progress:
            return

        progress = self._progress[sync_id]

        if failed:
            progress.failed_items += 1
        else:
            progress.processed_items += 1

        if current_item:
            progress.current_item = current_item

        if overall_percent is not None:
            progress.overall_percent = overall_percent

        # Emit event for significant milestones
        should_emit = False

        if progress.total_items > 0:
            pct = progress.overall_percent
            # Emit at key milestones (every ~3% overall)
            milestones = [1, 3, 5, 8, 10, 15, 20, 25, 30, 33, 35, 40, 45, 50,
                          55, 60, 66, 70, 75, 80, 85, 90, 95, 99]
            for m in milestones:
                if pct >= m and (pct - (1.0 if progress.total_items > 1 else 0)) < m:
                    should_emit = True
                    break

            # Also emit every 3 items for responsive feedback
            if not should_emit and progress.processed_items % 3 == 0:
                should_emit = True

            # Always emit on first and last item
            if progress.processed_items == 1 or progress.processed_items == progress.total_items:
                should_emit = True
        else:
            # If total unknown, emit every 3 items
            if progress.processed_items % 3 == 0 or progress.processed_items == 1:
                should_emit = True

        if should_emit:
            self._emit_event(sync_id, 'progress')

    def subscribe_email(self, sync_id: str, email: str):
        """Subscribe an email for notification when ALL syncs for this user complete"""
        if sync_id not in self._progress:
            print(f"[SyncProgress] WARNING: Cannot subscribe email - sync_id {sync_id} not found")
            return False

        progress = self._progress[sync_id]
        user_id = progress.user_id

        # Clear the email_sent flag when user explicitly subscribes
        # This allows them to receive a new email for this batch of syncs
        self._email_sent_for_user.discard(user_id)

        # Store at user level - will notify when ALL syncs complete
        self._user_email_subscriptions[user_id] = email
        # Also store on the sync for backward compatibility
        progress.notify_email = email

        print(f"[SyncProgress] Email notification subscribed for user {user_id}: {email} (will notify when ALL syncs complete)")
        return True

    def get_active_syncs_for_user(self, user_id: str) -> List[SyncProgress]:
        """Get all active (non-completed) syncs for a user"""
        return [
            p for p in self._progress.values()
            if p.user_id == user_id and p.status not in ('complete', 'completed', 'error')
        ]

    def get_completed_syncs_for_user(self, user_id: str) -> List[SyncProgress]:
        """Get all completed syncs for a user (for aggregated notification)"""
        return [
            p for p in self._progress.values()
            if p.user_id == user_id and p.status in ('complete', 'completed', 'error')
            and p.completed_at is not None
        ]

    def complete_sync(
        self,
        sync_id: str,
        error_message: Optional[str] = None
    ):
        """Mark sync as complete or failed, send email notification when ALL user syncs complete"""
        if sync_id not in self._progress:
            return

        progress = self._progress[sync_id]
        progress.completed_at = datetime.now(timezone.utc)

        if error_message:
            progress.status = 'error'
            progress.stage = 'Sync failed'
            progress.error_message = error_message
            self._emit_event(sync_id, 'error')
        else:
            progress.status = 'complete'
            progress.stage = 'Sync complete'
            progress.overall_percent = 100.0
            self._emit_event(sync_id, 'complete')

        print(f"[SyncProgress] Completed sync: {sync_id} - {progress.status}")

        # Check if ALL syncs for this user are complete
        user_id = progress.user_id
        active_syncs = self.get_active_syncs_for_user(user_id)

        if active_syncs:
            print(f"[SyncProgress] User {user_id} still has {len(active_syncs)} active syncs - waiting to send email")
            return

        # All syncs complete! Check for email subscription
        notify_email = self._user_email_subscriptions.get(user_id)

        if not notify_email:
            # Fallback: check database for notify_email persisted by subscribe endpoint
            try:
                from database.models import SessionLocal, Connector, User
                from sqlalchemy.orm.attributes import flag_modified
                db = SessionLocal()
                try:
                    # First check User.preferences (preferred method)
                    user = db.query(User).filter(User.id == user_id).first()
                    if user and user.preferences:
                        prefs = user.preferences
                        if prefs.get('sync_notify_enabled') and prefs.get('sync_notify_email'):
                            notify_email = prefs['sync_notify_email']
                            print(f"[SyncProgress] Found notify_email in User.preferences: {notify_email}")
                            # Clear after use
                            prefs['sync_notify_enabled'] = False
                            user.preferences = prefs
                            flag_modified(user, 'preferences')
                            db.commit()

                    # Fallback to Connector.settings if still not found
                    if not notify_email:
                        connectors = db.query(Connector).filter(
                            Connector.tenant_id == progress.tenant_id
                        ).all()
                        for c in connectors:
                            settings = c.settings or {}
                            if settings.get('notify_email'):
                                notify_email = settings['notify_email']
                                print(f"[SyncProgress] Found notify_email in Connector.settings: {notify_email}")
                                # Clear it so we don't re-send
                                settings.pop('notify_email', None)
                                c.settings = settings
                                flag_modified(c, 'settings')
                                db.commit()
                                break
                finally:
                    db.close()
            except Exception as db_err:
                print(f"[SyncProgress] DB fallback for notify_email failed: {db_err}")

        if notify_email:
            # Check if email was already sent for this user (prevents duplicates from multiple complete_sync calls)
            if user_id in self._email_sent_for_user:
                print(f"[SyncProgress] Email already sent for user {user_id}, skipping duplicate")
                return

            # Mark as sent BEFORE sending to prevent race conditions
            self._email_sent_for_user.add(user_id)

            # All syncs complete - send aggregated email
            self._send_batch_completion_email(user_id, notify_email)
            # Clear the subscription after sending
            self._user_email_subscriptions.pop(user_id, None)

    def _send_batch_completion_email(self, user_id: str, email: str):
        """Send email notification for all completed syncs"""
        completed_syncs = self.get_completed_syncs_for_user(user_id)
        if not completed_syncs:
            return

        try:
            from services.email_notification_service import get_email_service
            email_service = get_email_service()

            # Aggregate stats from all syncs
            total_items = sum(s.total_items for s in completed_syncs)
            processed_items = sum(s.processed_items for s in completed_syncs)
            failed_items = sum(s.failed_items for s in completed_syncs)
            connector_types = list(set(s.connector_type for s in completed_syncs))

            # Calculate total duration
            earliest_start = min((s.started_at for s in completed_syncs if s.started_at), default=None)
            latest_end = max((s.completed_at for s in completed_syncs if s.completed_at), default=None)
            total_duration = 0.0
            if earliest_start and latest_end:
                total_duration = (latest_end - earliest_start).total_seconds()

            # Check for any errors
            errors = [s.error_message for s in completed_syncs if s.error_message]
            error_message = "; ".join(errors) if errors else None

            # Format connector list
            connector_str = ", ".join(c.title() for c in connector_types)
            if len(connector_types) > 1:
                connector_str = f"All Integrations ({connector_str})"

            print(f"[SyncProgress] Sending batch completion email for {len(completed_syncs)} syncs: {connector_str}")

            success = email_service.send_sync_complete_notification(
                user_email=email,
                connector_type=connector_str,
                total_items=total_items,
                processed_items=processed_items,
                failed_items=failed_items,
                duration_seconds=total_duration,
                error_message=error_message
            )
            if success:
                print(f"[SyncProgress] Batch email notification sent to {email}")
            else:
                print(f"[SyncProgress] Batch email notification failed (SMTP not configured or send error)")
        except Exception as e:
            print(f"[SyncProgress] Failed to send batch email notification: {e}")

    def get_progress(self, sync_id: str) -> Optional[Dict]:
        """Get current progress for a sync"""
        progress = self._progress.get(sync_id)
        return progress.to_dict() if progress else None

    def get_active_by_tenant_type(self, tenant_id: str, connector_type: str) -> Optional[Dict]:
        """Find active sync by tenant and connector type (for polling fallback)"""
        for sync_id, progress in self._progress.items():
            if (progress.tenant_id == tenant_id and
                progress.connector_type == connector_type and
                progress.status not in ('complete', 'error')):
                return progress.to_dict()
        return None

    # Max SSE subscribers per sync_id to prevent memory leaks from reconnecting browsers
    MAX_SUBSCRIBERS_PER_SYNC = 3

    def subscribe(self, sync_id: str) -> queue.Queue:
        """
        Subscribe to progress events for a sync.
        Synchronous method - uses standard library queue for gevent compatibility.
        Limits subscribers to MAX_SUBSCRIBERS_PER_SYNC per sync_id.

        Returns:
            Queue that will receive progress events
        """
        # Evict oldest subscribers if at capacity
        subs = self._subscribers[sync_id]
        while len(subs) >= self.MAX_SUBSCRIBERS_PER_SYNC:
            old_q = subs.pop(0)
            # Signal the old subscriber to close
            try:
                old_q.put_nowait({'event': 'evicted', 'data': {'reason': 'new subscriber connected'}})
            except queue.Full:
                pass
            print(f"[SyncProgress] Evicted oldest subscriber for {sync_id} (was at {len(subs) + 1})")

        q = queue.Queue(maxsize=100)
        subs.append(q)

        # Send current state immediately
        if sync_id in self._progress:
            try:
                q.put_nowait({
                    'event': 'current_state',
                    'data': self._progress[sync_id].to_dict()
                })
            except queue.Full:
                pass

        print(f"[SyncProgress] New subscriber for {sync_id} (total: {len(subs)})")
        return q

    def unsubscribe(self, sync_id: str, q: queue.Queue):
        """Unsubscribe from progress events"""
        if sync_id in self._subscribers:
            if q in self._subscribers[sync_id]:
                self._subscribers[sync_id].remove(q)
                print(f"[SyncProgress] Unsubscribed from {sync_id}")

    def _emit_event(self, sync_id: str, event_type: str):
        """Emit event to all subscribers"""
        if sync_id not in self._progress:
            return

        progress = self._progress[sync_id]
        event = {
            'event': event_type,
            'data': progress.to_dict()
        }

        # Send to all subscribers (non-blocking)
        if sync_id in self._subscribers:
            for q in self._subscribers[sync_id]:
                try:
                    q.put_nowait(event)
                except queue.Full:
                    print(f"[SyncProgress] Queue full for subscriber, skipping event")

    def _periodic_cleanup(self):
        """Periodically clean up old syncs to prevent memory leaks"""
        import time
        while True:
            time.sleep(300)  # Every 5 minutes
            try:
                self.cleanup_old_syncs()
            except Exception as e:
                print(f"[SyncProgress] Cleanup error: {e}")

    def cleanup_old_syncs(self, max_age_seconds: int = 3600):
        """Remove completed syncs older than max_age and mark stuck syncs as error"""
        now = datetime.now(timezone.utc)
        to_remove = []
        stuck_timeout = 1800  # 30 minutes — if no update, assume stuck

        for sync_id, progress in list(self._progress.items()):
            if progress.completed_at:
                # Remove completed syncs after max_age
                age = (now - progress.completed_at).total_seconds()
                if age > max_age_seconds:
                    to_remove.append(sync_id)
            elif progress.started_at:
                # Detect stuck syncs (no completion after 30 min)
                age = (now - progress.started_at).total_seconds()
                if age > stuck_timeout and progress.status not in ('complete', 'error'):
                    print(f"[SyncProgress] Stuck sync detected: {sync_id} (status={progress.status}, age={age:.0f}s)")
                    progress.status = 'error'
                    progress.stage = 'Sync timed out'
                    progress.error_message = f'Sync appears stuck after {int(age/60)} minutes'
                    progress.completed_at = now
                    self._emit_event(sync_id, 'error')
                    # Also reset connector status in DB
                    try:
                        from database.models import SessionLocal, Connector, ConnectorStatus
                        db = SessionLocal()
                        try:
                            from sqlalchemy import and_
                            connector = db.query(Connector).filter(
                                Connector.tenant_id == progress.tenant_id,
                                Connector.status == ConnectorStatus.SYNCING
                            ).first()
                            if connector:
                                settings = connector.settings or {}
                                if settings.get('current_sync_id') == sync_id:
                                    connector.status = ConnectorStatus.CONNECTED
                                    connector.error_message = f'Sync timed out after {int(age/60)} minutes'
                                    db.commit()
                                    print(f"[SyncProgress] Reset stuck connector to CONNECTED")
                        finally:
                            db.close()
                    except Exception as db_err:
                        print(f"[SyncProgress] Failed to reset stuck connector: {db_err}")

        for sync_id in to_remove:
            del self._progress[sync_id]
            if sync_id in self._subscribers:
                del self._subscribers[sync_id]
            print(f"[SyncProgress] Cleaned up old sync: {sync_id}")


# Global instance
_sync_progress_service = None

def get_sync_progress_service() -> SyncProgressService:
    """Get the global SyncProgressService instance"""
    global _sync_progress_service
    if _sync_progress_service is None:
        _sync_progress_service = SyncProgressService()
    return _sync_progress_service
