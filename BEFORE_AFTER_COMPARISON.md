# Before/After Code Comparison - GitHub Sync Fix

---

## 🔴 BEFORE (Broken - Would Hang Forever)

### `github_connector.py` - Line 86
```python
# ❌ NO TIMEOUT!
response = requests.post(
    'https://github.com/login/oauth/access_token',
    headers={'Accept': 'application/json'},
    data={
        'client_id': self.client_id,
        'client_secret': self.client_secret,
        'code': code,
        'redirect_uri': self.redirect_uri
    }
)
```

**Problem:** If GitHub OAuth server is slow or unresponsive, this request **hangs forever**.

---

### `github_connector.py` - Line 149
```python
# ❌ NO TIMEOUT!
while True:  # ← Infinite loop!
    response = requests.get(
        f'{self.base_url}/user/repos',
        headers=self.headers,
        params={'per_page': per_page, 'page': page}
    )
    # ... process repos
    page += 1  # Could go forever!
```

**Problem:**
- HTTP request has **no timeout**
- Loop has **no maximum iterations**
- Could run **forever**

---

### `connector_manager.py` - Line 138
```python
# ❌ NO TIMEOUT!
connected = await connector.connect()
if not connected:
    return {"success": False, "error": connector.last_error or "Failed to connect"}
```

**Problem:** If `connector.connect()` hangs, the entire request **hangs forever**. User sees "Connecting..." indefinitely.

---

### `connector_manager.py` - Line 197
```python
# ❌ NO TIMEOUT!
documents = await connector.sync(since)
```

**Problem:** If sync takes 30+ minutes, user has **no feedback**. Could be processing or could be stuck - no way to know!

---

## 🟢 AFTER (Fixed - Times Out Gracefully)

### `github_connector.py` - Line 27-30 (NEW)
```python
# ✅ ADDED TIMEOUT CONSTANTS
# HTTP request timeout in seconds
REQUEST_TIMEOUT = 30

# Maximum iterations for pagination to prevent infinite loops
MAX_PAGINATION_ITERATIONS = 100
```

---

### `github_connector.py` - Line 86 (FIXED)
```python
# ✅ NOW HAS 30 SECOND TIMEOUT!
response = requests.post(
    'https://github.com/login/oauth/access_token',
    headers={'Accept': 'application/json'},
    data={
        'client_id': self.client_id,
        'client_secret': self.client_secret,
        'code': code,
        'redirect_uri': self.redirect_uri
    },
    timeout=self.REQUEST_TIMEOUT  # ← ADDED THIS!
)
```

**Fix:** Request **fails after 30 seconds** if GitHub doesn't respond.

---

### `github_connector.py` - Line 157 (FIXED)
```python
# ✅ NOW HAS TIMEOUT AND LOOP LIMIT!
while page <= self.MAX_PAGINATION_ITERATIONS:  # ← Max 100 pages
    response = requests.get(
        f'{self.base_url}/user/repos',
        headers=self.headers,
        params={'per_page': per_page, 'page': page},
        timeout=self.REQUEST_TIMEOUT  # ← ADDED THIS!
    )
    # ... process repos
    page += 1

if page > self.MAX_PAGINATION_ITERATIONS:
    print(f"[GitHub] Warning: Hit pagination limit of {self.MAX_PAGINATION_ITERATIONS} pages")
```

**Fix:**
- HTTP request **times out after 30 seconds**
- Loop **stops after 100 iterations** max
- **Warning logged** if limit hit

---

### `connector_manager.py` - Line 32-33 (NEW)
```python
# ✅ ADDED TIMEOUT CONSTANTS
# Timeouts in seconds
CONNECTION_TIMEOUT = 60  # Max time to wait for OAuth connection
SYNC_TIMEOUT = 600  # Max time to wait for sync (10 minutes)
```

---

### `connector_manager.py` - Line 143 (FIXED)
```python
# ✅ NOW HAS 60 SECOND TIMEOUT!
try:
    print(f"[ConnectorManager] Attempting to connect {connector_type} for user {user_id}...")
    connected = await asyncio.wait_for(
        connector.connect(),
        timeout=self.CONNECTION_TIMEOUT  # ← ADDED THIS!
    )
    if not connected:
        error_msg = connector.last_error or "Failed to connect"
        print(f"[ConnectorManager] Connection failed: {error_msg}")
        return {"success": False, "error": error_msg}
    print(f"[ConnectorManager] Successfully connected {connector_type}")

except asyncio.TimeoutError:  # ← CATCH TIMEOUT!
    error_msg = f"Connection timeout after {self.CONNECTION_TIMEOUT} seconds"
    print(f"[ConnectorManager] {error_msg}")
    return {"success": False, "error": error_msg}

except Exception as e:  # ← CATCH OTHER ERRORS!
    error_msg = f"Connection error: {str(e)}"
    print(f"[ConnectorManager] {error_msg}")
    return {"success": False, "error": error_msg}
```

**Fix:**
- Connection **times out after 60 seconds**
- **Clear error message** returned to user
- **Logs progress** to console

---

### `connector_manager.py` - Line 226 (FIXED)
```python
# ✅ NOW HAS 10 MINUTE TIMEOUT AND PROGRESS LOGGING!
try:
    print(f"[ConnectorManager] Starting sync for {connector_type} (user: {user_id})...")
    start_time = datetime.now()

    # Sync with timeout
    documents = await asyncio.wait_for(
        connector.sync(since),
        timeout=self.SYNC_TIMEOUT  # ← ADDED THIS! (600 seconds = 10 min)
    )

    duration = (datetime.now() - start_time).total_seconds()
    print(f"[ConnectorManager] Sync completed in {duration:.1f}s - {len(documents)} documents")

    # ... rest of success handling

except asyncio.TimeoutError:  # ← CATCH TIMEOUT!
    duration = (datetime.now() - start_time).total_seconds()
    error_msg = f"Sync timeout after {self.SYNC_TIMEOUT} seconds"
    print(f"[ConnectorManager] {error_msg}")
    return {"success": False, "error": error_msg}

except Exception as e:  # ← CATCH OTHER ERRORS!
    duration = (datetime.now() - start_time).total_seconds()
    error_msg = str(e)
    print(f"[ConnectorManager] Sync error: {error_msg}")
    return {"success": False, "error": error_msg}
```

**Fix:**
- Sync **times out after 10 minutes**
- **Logs progress** at start and end
- **Tracks duration** of sync
- **Clear error messages** when timeout occurs

---

## 📊 Summary of Changes

| Location | Before | After | Impact |
|----------|--------|-------|--------|
| HTTP Requests (7 places) | No timeout | 30s timeout | Fails fast on network issues |
| Pagination Loop | Infinite loop possible | Max 100 iterations | Prevents runaway loops |
| Connection | No timeout | 60s timeout | OAuth won't hang forever |
| Sync | No timeout | 10 min timeout | Large repos fail gracefully |
| Logging | Silent | Progress logged | Can see what's happening |
| Error Handling | Generic | Specific timeout errors | Clear user feedback |

---

## 🎯 Result

### Before:
```
User clicks "Sync" → Stuck at "0% complete - Connecting..." → Wait forever → Give up
```

### After:
```
User clicks "Sync" → Backend logs progress → Either:
  ✅ Success: "Sync completed in 45.3s - 150 documents"
  ⏱️ Timeout: "Sync timeout after 600 seconds" (clear error shown)
  ❌ Error: Specific error message (e.g., "Connection timeout after 60 seconds")
```

---

**All 7 HTTP requests** now have timeouts.
**All async operations** now have timeouts.
**All loops** now have maximum iterations.
**All errors** are logged and returned to user.

✅ **No more infinite hangs!**
