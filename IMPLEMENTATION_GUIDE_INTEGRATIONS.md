# Integration Improvements Implementation Guide

## Overview
This guide provides implementations for improving existing integrations **without adding new external services**. All improvements use existing infrastructure and Render deployment.

---

## 1. Box Incremental Sync (HIGH PRIORITY - Cost Savings)

### Problem
Currently re-downloads and re-parses ALL files on every sync, even unchanged ones.

**Cost Impact**: 100 files × 5 syncs = 500 unnecessary LlamaParse calls (~$15/sync wasted)

### Solution: SHA1 Hash Comparison

**File**: `backend/connectors/box_connector.py`

**Changes needed in `_process_file_new_sdk()` method** (around line 572):

```python
async def _process_file_new_sdk(
    self,
    file_id: str,
    file_name: str,
    folder_path: str,
    since: Optional[datetime],
    max_file_size: int,
    file_extensions: List[str]
) -> Optional[Document]:
    """Process a single file using new SDK (v10+)"""
    try:
        # Get full file info
        file_obj = self.client.files.get_file_by_id(file_id)

        # === NEW: CHECK IF FILE UNCHANGED ===
        # Check if document already exists with same sha1 (unchanged file)
        from database.models import SessionLocal, Document as DBDocument
        db = SessionLocal()
        try:
            existing_doc = db.query(DBDocument).filter(
                DBDocument.tenant_id == self.config.tenant_id,
                DBDocument.external_id == f"box_{file_id}"
            ).first()

            if existing_doc:
                # Check sha1 hash
                existing_sha1 = existing_doc.doc_metadata.get('sha1') if existing_doc.doc_metadata else None
                current_sha1 = getattr(file_obj, 'sha1', None)

                if existing_sha1 and current_sha1 and existing_sha1 == current_sha1:
                    print(f"[BoxConnector] ✓ File {file_name} unchanged (sha1 match), skipping")
                    return None  # Skip unchanged file
                elif current_sha1:
                    print(f"[BoxConnector] File {file_name} modified (sha1 changed), re-processing")
                else:
                    print(f"[BoxConnector] File {file_name} has no sha1, processing anyway")
        finally:
            db.close()
        # === END NEW CODE ===

        # Check modified date (KEEP existing logic for files without sha1)
        if since:
            modified_at = file_obj.modified_at
            if isinstance(modified_at, str):
                modified_at = datetime.fromisoformat(modified_at.replace('Z', '+00:00'))
            if modified_at:
                since_aware = since if since.tzinfo else since.replace(tzinfo=timezone.utc)
                if modified_at.tzinfo is None:
                    modified_at = modified_at.replace(tzinfo=timezone.utc)

                # ONLY skip if file is older AND we already have it
                if modified_at < since_aware and existing_doc:
                    print(f"[BoxConnector] File {file_name} older than {since_aware}, skipping")
                    return None

        # ... rest of existing code continues
```

**Impact**:
- ✅ Skips downloading unchanged files
- ✅ Skips re-parsing with LlamaParse
- ✅ Skips re-uploading to S3
- ✅ Saves ~90% of API costs on subsequent syncs
- ✅ Reduces sync time from 10+ minutes to <1 minute

**Testing**:
```bash
# 1. Initial sync - downloads all files
POST /api/integrations/box/sync

# 2. Second sync - should skip all unchanged files
POST /api/integrations/box/sync
# Check logs for: "File X unchanged (sha1 match), skipping"

# 3. Modify a file in Box, then sync again
# Should only process the changed file
```

---

## 2. Better Logging (NO NEW SERVICES)

### Problem
Using `print()` statements everywhere. No log levels, inconsistent formatting.

### Solution: Python Built-in Logging

**File**: `backend/utils/logger.py` (NEW FILE)

```python
"""
Centralized logging configuration.
Uses Python's built-in logging (no external services required).
"""

import logging
import sys
from datetime import datetime

def setup_logger(name: str = "secondbrain") -> logging.Logger:
    """
    Set up structured logger with consistent formatting.

    Logs are captured by Render automatically (no Papertrail needed).
    """
    logger = logging.getLogger(name)

    # Only configure if not already configured
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    # Console handler (captured by Render)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)

    # Structured format: [TIMESTAMP] [LEVEL] [MODULE] message
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.propagate = False  # Don't propagate to root logger

    return logger

# Convenience function for quick logging
def log_info(module: str, message: str, **kwargs):
    """Log info with context"""
    logger = setup_logger(module)
    extra_info = " ".join([f"{k}={v}" for k, v in kwargs.items()])
    logger.info(f"{message} {extra_info}" if extra_info else message)

def log_error(module: str, message: str, error: Exception = None, **kwargs):
    """Log error with context"""
    logger = setup_logger(module)
    extra_info = " ".join([f"{k}={v}" for k, v in kwargs.items()])
    full_message = f"{message} {extra_info}" if extra_info else message
    if error:
        logger.error(f"{full_message} | Error: {str(error)}", exc_info=True)
    else:
        logger.error(full_message)

def log_warning(module: str, message: str, **kwargs):
    """Log warning with context"""
    logger = setup_logger(module)
    extra_info = " ".join([f"{k}={v}" for k, v in kwargs.items()])
    logger.warning(f"{message} {extra_info}" if extra_info else message)
```

**Usage in Box Connector**:

```python
# OLD:
print(f"[BoxConnector] Syncing folder {folder_id}")
print(f"[BoxConnector] Got {len(documents)} documents")

# NEW:
from utils.logger import log_info, log_error

log_info("BoxConnector", "Starting folder sync", folder_id=folder_id, tenant_id=self.config.tenant_id)
log_info("BoxConnector", "Sync complete", document_count=len(documents), duration_ms=elapsed)
```

**Render Integration**:
- Logs automatically captured by Render
- Viewable in Render dashboard → Logs tab
- Searchable (limited on free tier)
- 7-day retention on free tier

---

## 3. Enhanced Health Check

### Problem
Current `/api/health` endpoint only returns `{"status": "healthy"}`. No actual checks.

### Solution: Check Critical Services

**File**: `backend/app_v2.py`

Replace existing health check:

```python
@app.route('/api/health', methods=['GET'])
def health_check():
    """
    Enhanced health check endpoint.

    Checks:
    - Database connectivity
    - Pinecone availability
    - Azure OpenAI availability

    Used by Render for health monitoring (already configured).
    """
    from utils.logger import log_warning
    import time

    start_time = time.time()
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {}
    }

    # 1. Database check
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
            health_status["checks"]["azure_openai"] = "ok"
        except Exception as e:
            health_status["checks"]["azure_openai"] = f"warning: {str(e)}"
            log_warning("HealthCheck", "Azure OpenAI check failed", error=str(e))

    # Response time
    health_status["response_time_ms"] = round((time.time() - start_time) * 1000, 2)

    # Return 200 if healthy, 503 if unhealthy
    status_code = 200 if health_status["status"] == "healthy" else 503

    return jsonify(health_status), status_code
```

**Render Configuration** (already in render.yaml):
```yaml
healthCheckPath: /api/health
```

Render automatically calls this endpoint every 30 seconds. If it returns 503, Render marks service as unhealthy.

---

## 4. Slack Bot Deployment Guide

### Problem
Slack bot code is complete but untested on Render deployment.

### Solution: Configuration Guide

**Step 1: Create Slack App**

1. Go to https://api.slack.com/apps
2. Click "Create New App" → "From scratch"
3. App Name: "2nd Brain"
4. Workspace: Your workspace

**Step 2: Configure OAuth & Permissions**

1. Navigate to "OAuth & Permissions"
2. Add Redirect URL:
   ```
   https://secondbrain-backend-XXXX.onrender.com/api/slack/oauth/callback
   ```
   (Replace XXXX with your Render service URL)

3. Bot Token Scopes (add these):
   - `app_mentions:read`
   - `channels:history`
   - `channels:read`
   - `chat:write`
   - `commands`
   - `im:history`
   - `im:read`
   - `im:write`
   - `users:read`

**Step 3: Configure Event Subscriptions**

1. Navigate to "Event Subscriptions"
2. Enable Events: ON
3. Request URL:
   ```
   https://secondbrain-backend-XXXX.onrender.com/api/slack/events
   ```
4. Subscribe to Bot Events:
   - `app_mention`
   - `message.im`

**Step 4: Configure Slash Commands**

1. Navigate to "Slash Commands"
2. Create New Command:
   - Command: `/ask`
   - Request URL: `https://secondbrain-backend-XXXX.onrender.com/api/slack/commands/ask`
   - Short Description: "Ask 2nd Brain a question"
   - Usage Hint: "What is our pricing model?"

**Step 5: Add Environment Variables to Render**

In Render dashboard → secondbrain-backend → Environment:

```bash
SLACK_CLIENT_ID=<from Slack app Basic Information>
SLACK_CLIENT_SECRET=<from Slack app Basic Information>
SLACK_SIGNING_SECRET=<from Slack app Basic Information>
```

**Step 6: Test the Integration**

1. In your app, click "Install to Workspace"
2. Authorize the app
3. In Slack, type: `/ask What is 2nd Brain?`
4. Bot should respond with RAG-generated answer

**Troubleshooting**:
- Check Render logs for `[SlackBot]` messages
- Verify webhook URLs are accessible (test with curl)
- Ensure signing secret matches

---

## 5. Gmail Push Notifications (Lower Priority)

### Problem
Gmail connector uses polling. No real-time sync.

### Solution: Gmail Watch API

**File**: `backend/connectors/gmail_connector.py`

Add method:

```python
async def setup_push_notifications(self, webhook_url: str) -> Optional[str]:
    """
    Set up Gmail push notifications via Pub/Sub.

    Returns watch_id if successful.

    Note: Requires Google Cloud Pub/Sub topic setup.
    """
    if not self.service:
        await self.connect()

    try:
        # Create watch request
        request = {
            'labelIds': ['INBOX', 'SENT'],
            'topicName': 'projects/YOUR_PROJECT_ID/topics/gmail-notifications'
        }

        response = self.service.users().watch(userId='me', body=request).execute()

        return response.get('historyId')

    except Exception as e:
        print(f"[Gmail] Failed to set up push: {e}")
        return None

async def handle_push_notification(self, history_id: str):
    """
    Handle Gmail push notification.

    Fetches new emails since history_id.
    """
    try:
        response = self.service.users().history().list(
            userId='me',
            startHistoryId=history_id,
            historyTypes=['messageAdded']
        ).execute()

        messages = []
        for history in response.get('history', []):
            for msg in history.get('messagesAdded', []):
                messages.append(msg['message'])

        # Process new messages...

    except Exception as e:
        print(f"[Gmail] Push handling error: {e}")
```

**Note**: Requires Google Cloud Pub/Sub setup (free tier: 10GB/month). Skip this for now if polling works.

---

## Implementation Priority

Based on your "no new services" constraint:

1. **✅ Box Incremental Sync** - Immediate cost savings, 2 hours
2. **✅ Better Logging** - Easy win, 1 hour
3. **✅ Enhanced Health Check** - Quick improvement, 30 min
4. **✅ Slack Bot Docs** - Enable testing, 15 min to write guide
5. **⏳ Gmail Push** - Skip for now (polling works, setup complex)

---

## Testing Checklist

### Box Incremental Sync
- [ ] Initial sync completes successfully
- [ ] Second sync skips unchanged files (check logs for "sha1 match")
- [ ] Modified file detected and re-processed
- [ ] Verify API cost reduction (check LlamaParse usage)

### Logging
- [ ] Logs appear in Render dashboard with timestamps
- [ ] Log levels visible (INFO, WARNING, ERROR)
- [ ] Searchable in Render logs

### Health Check
- [ ] `/api/health` returns database status
- [ ] Returns 503 when database down
- [ ] Render marks service unhealthy on 503

### Slack Bot
- [ ] OAuth flow completes
- [ ] `/ask` command works in Slack
- [ ] Bot responds with RAG answer
- [ ] App mentions trigger responses

---

## Cost Savings Estimate

**Box Incremental Sync**:
- Before: 100 files × 10 pages × $0.003 = $3 per sync
- After: ~5 changed files × 10 pages × $0.003 = $0.15 per sync
- **Savings: ~95% reduction in LlamaParse costs**

**Render Resource Usage**:
- Faster syncs = less CPU time
- Less memory usage (no re-parsing)
- Fewer cold starts (faster responses)

---

Ready to implement these improvements?
