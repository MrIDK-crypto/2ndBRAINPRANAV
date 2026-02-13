# Testing Instructions - GitHub Sync Fixes

**Date:** 2026-01-31
**Status:** ✅ Backend Running on http://localhost:5003

---

## 🎯 What Was Fixed

### 1. HTTP Request Timeouts
- ✅ All GitHub API calls now timeout after 30 seconds
- ✅ Prevents indefinite hanging on slow/failed connections

### 2. Connection Timeouts
- ✅ OAuth connection times out after 60 seconds
- ✅ Clear error messages when timeout occurs

### 3. Sync Timeouts
- ✅ Sync operation times out after 10 minutes (600 seconds)
- ✅ Duration tracking and logging added

### 4. Pagination Limits
- ✅ Maximum 100 pages of repositories (prevents infinite loops)
- ✅ Warning logged if limit is hit

---

## 🚀 Backend is Running!

**Backend URL:** http://localhost:5003
**Health Check:** http://localhost:5003/api/health

**To check status:**
```bash
curl http://localhost:5003/api/health
# Should return: {"status":"ok"}
```

---

## 🧪 How to Test the Fixes

### Step 1: Access the Frontend

Open your browser and navigate to your frontend URL (usually http://localhost:3000 or http://localhost:3006)

### Step 2: Navigate to Integrations

1. Log in to your 2ndBrain application
2. Go to the "Integrations" page
3. Find the "GitHub" integration

### Step 3: Test Connection

1. Click "Connect GitHub" button
2. You'll be redirected to GitHub for authorization
3. **Watch for:**
   - If GitHub is slow, you'll see an error after 60 seconds (connection timeout)
   - Backend console will show: `[ConnectorManager] Attempting to connect github for user ...`

### Step 4: Test Sync

1. After successful connection, click "Sync" button
2. **Watch the backend console** for progress logs:
   ```
   [ConnectorManager] Starting sync for github (user: ...)...
   [GitHub] Fetching repository tree: owner/repo
   [GitHub] Found N total items in repository
   [GitHub] Filtered to M code files
   [GitHub] [1/M] Fetching: file1.py
   [GitHub] [2/M] Fetching: file2.py
   ...
   [ConnectorManager] Sync completed in X.Xs - N documents
   ```

3. **If sync takes too long:**
   - After 10 minutes, you'll see: `[ConnectorManager] Sync timeout after 600 seconds`
   - Frontend will show an error message

---

## 📊 Backend Console Logs

### Normal Operation:
```bash
[ConnectorManager] Attempting to connect github for user abc123...
[ConnectorManager] Successfully connected github
[ConnectorManager] Starting sync for github (user: abc123)...
[GitHub] Fetching repository tree: MrIDK-crypto/2ndBrainFINAL
[GitHub] Found 200 total items in repository
[GitHub] Filtered to 150 code files
[GitHub] [1/150] Fetching: backend/app_v2.py
[GitHub] [2/150] Fetching: backend/connectors/github_connector.py
...
[ConnectorManager] Sync completed in 45.3s - 150 documents
```

### Connection Timeout:
```bash
[ConnectorManager] Attempting to connect github for user abc123...
[ConnectorManager] Connection timeout after 60 seconds
```

### Sync Timeout:
```bash
[ConnectorManager] Starting sync for github (user: abc123)...
[GitHub] Fetching repository tree: huge-repo/massive-codebase
...
[ConnectorManager] Sync timeout after 600 seconds
```

### HTTP Timeout (GitHub API slow):
```bash
[GitHub] Error fetching src/main.py: HTTPSConnectionPool(host='api.github.com'): Read timed out. (read timeout=30)
```

---

## 🔍 Watch the Backend Console

**To see the logs in real-time:**

```bash
# If backend is running in background, check the task output:
# The backend is running as task: be212b8

# Or restart it in foreground to see logs:
cd /Users/badri/2ndBrainFINAL/backend
./venv_fixed/bin/python app_v2.py
```

You'll see clear progress messages showing exactly what's happening!

---

## ⚙️ Configuration

Current timeout values (can be adjusted in the code if needed):

| Setting | Value | File | Line |
|---------|-------|------|------|
| HTTP Request Timeout | 30s | `github_connector.py` | Line 30 |
| Connection Timeout | 60s | `connector_manager.py` | Line 29 |
| Sync Timeout | 600s (10 min) | `connector_manager.py` | Line 30 |
| Max Pagination | 100 pages | `github_connector.py` | Line 33 |

---

## ✅ Success Criteria

The fix is working if:
- ✅ Sync no longer hangs indefinitely at "0% complete"
- ✅ Clear error messages appear when timeouts occur
- ✅ Backend logs show progress during sync
- ✅ Can reconnect/retry after timeout

---

## 🐛 If You Still See Issues

### Issue: Still stuck at "Connecting..."

**Check:**
1. Is backend actually running? → `curl http://localhost:5003/api/health`
2. Check backend console for errors
3. Check browser console (F12) for JavaScript errors

### Issue: Timeout happens too fast

**Solution:** Increase timeout values:
```python
# In github_connector.py, line 30:
REQUEST_TIMEOUT = 60  # Increase from 30 to 60

# In connector_manager.py, line 30:
SYNC_TIMEOUT = 1200  # Increase from 600 to 1200 (20 min)
```

### Issue: Frontend still shows "0% complete"

**Note:** This is expected! The frontend UI doesn't have real-time progress updates (that would require WebSocket implementation). The fixes ensure:
- Backend doesn't hang forever
- Clear error messages when timeout occurs
- Progress is logged to backend console

**For real-time UI updates, you'd need to implement:**
- WebSocket connection between frontend and backend
- Progress events sent from backend during sync
- Frontend UI updates based on events

---

## 📞 Need Help?

**Check these locations:**
1. **Backend logs** - Console where `app_v2.py` is running
2. **Fix summary** - `/Users/badri/2ndBrainFINAL/GITHUB_SYNC_FIX_SUMMARY.md`
3. **Modified files:**
   - `/Users/badri/2ndBrainFINAL/backend/connectors/github_connector.py`
   - `/Users/badri/2ndBrainFINAL/backend/connectors/connector_manager.py`

---

**Happy Testing!** 🚀

The sync should now fail gracefully with clear error messages instead of hanging forever.
