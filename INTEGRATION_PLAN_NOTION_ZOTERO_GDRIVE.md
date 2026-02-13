# Integration Plan: Notion, Zotero, Google Drive

## Executive Summary

This plan adds three new integrations to 2nd Brain:
1. **Notion** - Sync pages and databases (OAuth 2.0)
2. **Zotero** - Sync research papers and annotations (OAuth 1.0a + API key fallback)
3. **Google Drive** - Sync documents and files (OAuth 2.0, shares infrastructure with Gmail)

**Estimated Files to Create:** 6 new files
**Estimated Files to Modify:** 5 existing files
**Dependencies to Add:** 3 Python packages

---

## Pre-Implementation Checklist

### OAuth App Registration Required

| Integration | Developer Portal | Credentials Needed |
|-------------|------------------|-------------------|
| Notion | https://www.notion.so/my-integrations | Client ID, Client Secret |
| Zotero | https://www.zotero.org/oauth/apps | Client Key, Client Secret (OAuth 1.0a) |
| Google Drive | https://console.cloud.google.com | Client ID, Client Secret (reuse Gmail app) |

### Environment Variables to Add

```bash
# Notion
NOTION_CLIENT_ID=
NOTION_CLIENT_SECRET=
NOTION_REDIRECT_URI=http://localhost:5003/api/integrations/notion/callback

# Zotero (OAuth 1.0a - different flow)
ZOTERO_CLIENT_KEY=
ZOTERO_CLIENT_SECRET=
ZOTERO_REDIRECT_URI=http://localhost:5003/api/integrations/zotero/callback

# Google Drive (can reuse existing Google OAuth app - just add scopes)
# Uses existing GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
GDRIVE_REDIRECT_URI=http://localhost:5003/api/integrations/gdrive/callback
```

### Python Dependencies

```bash
pip install notion-client      # Notion SDK
pip install pyzotero           # Zotero API client
# google-api-python-client already installed (used by Gmail)
```

---

## Phase 1: Database Schema Updates

### File: `backend/database/models.py`

**Add to ConnectorType enum:**

```python
class ConnectorType(PyEnum):
    """Supported integration types"""
    GMAIL = "gmail"
    SLACK = "slack"
    BOX = "box"
    GITHUB = "github"
    ONEDRIVE = "onedrive"
    WEBSCRAPER = "webscraper"
    EMAIL_FORWARDING = "email_forwarding"
    PUBMED = "pubmed"
    # NEW INTEGRATIONS
    NOTION = "notion"
    ZOTERO = "zotero"
    GDRIVE = "gdrive"
```

**No other schema changes needed** - existing Document and Connector models support all required fields.

---

## Phase 2: Notion Integration

### 2.1 Overview

| Aspect | Details |
|--------|---------|
| Auth Type | OAuth 2.0 |
| API | Notion API v1 |
| SDK | `notion-client` |
| Sync Content | Pages, Database entries, Blocks |
| Document Type | `document` |

### 2.2 Create Connector

**File:** `backend/connectors/notion_connector.py`

```python
"""
Notion Connector for 2nd Brain
Syncs pages and database entries from Notion workspaces
"""

import os
import asyncio
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from connectors.base_connector import (
    BaseConnector,
    ConnectorConfig,
    ConnectorStatus,
    Document
)

try:
    from notion_client import Client
    NOTION_AVAILABLE = True
except ImportError:
    NOTION_AVAILABLE = False


class NotionConnector(BaseConnector):
    """Connector for Notion workspaces"""

    CONNECTOR_TYPE = "notion"
    REQUIRED_CREDENTIALS = ["access_token"]
    OPTIONAL_SETTINGS = {
        "database_ids": [],           # Specific databases to sync (empty = all)
        "include_archived": False,    # Include archived pages
        "max_blocks_per_page": 200,   # Limit blocks fetched per page
        "sync_comments": False        # Include page comments
    }

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.client: Optional[Client] = None
        self.workspace_name: str = ""
        self.workspace_id: str = ""

    async def connect(self) -> bool:
        """Establish connection to Notion API"""
        if not NOTION_AVAILABLE:
            self._set_error("Notion SDK not installed. Run: pip install notion-client")
            return False

        try:
            self.status = ConnectorStatus.CONNECTING
            access_token = self.config.credentials.get("access_token")

            if not access_token:
                self._set_error("Missing access_token in credentials")
                return False

            # Initialize client
            self.client = Client(auth=access_token)

            # Test connection and get workspace info
            me = self.client.users.me()
            self.workspace_name = me.get("name", "Notion Workspace")

            # Get bot info for workspace details
            bot_info = me.get("bot", {})
            owner = bot_info.get("owner", {})
            if owner.get("type") == "workspace":
                self.workspace_id = owner.get("workspace", {}).get("id", "")

            self.status = ConnectorStatus.CONNECTED
            self._clear_error()
            print(f"[Notion] Connected to workspace: {self.workspace_name}")
            return True

        except Exception as e:
            self._set_error(f"Connection failed: {str(e)}")
            return False

    async def disconnect(self) -> bool:
        """Disconnect from Notion"""
        self.client = None
        self.status = ConnectorStatus.DISCONNECTED
        return True

    async def test_connection(self) -> bool:
        """Verify connection is still valid"""
        if not self.client:
            return False
        try:
            self.client.users.me()
            return True
        except Exception:
            return False

    async def sync(self, since: Optional[datetime] = None) -> List[Document]:
        """
        Sync pages and database entries from Notion

        Args:
            since: Only sync items modified after this time (incremental sync)

        Returns:
            List of Document objects
        """
        if not self.client:
            connected = await self.connect()
            if not connected:
                return []

        self.status = ConnectorStatus.SYNCING
        documents = []

        try:
            # Build filter for incremental sync
            filter_params = {}
            if since:
                filter_params["filter"] = {
                    "timestamp": "last_edited_time",
                    "last_edited_time": {
                        "after": since.isoformat()
                    }
                }

            # Search for all pages (includes database pages)
            print(f"[Notion] Starting sync (since={since})")

            has_more = True
            start_cursor = None
            page_count = 0

            while has_more:
                search_params = {
                    "filter": {"property": "object", "value": "page"},
                    "sort": {
                        "direction": "descending",
                        "timestamp": "last_edited_time"
                    },
                    "page_size": 100
                }

                if start_cursor:
                    search_params["start_cursor"] = start_cursor

                results = self.client.search(**search_params)

                for page in results.get("results", []):
                    # Skip if before since date (for incremental)
                    if since:
                        last_edited = page.get("last_edited_time", "")
                        if last_edited:
                            edited_dt = datetime.fromisoformat(last_edited.replace("Z", "+00:00"))
                            if edited_dt < since:
                                continue

                    # Skip archived if not configured
                    if page.get("archived") and not self.config.settings.get("include_archived"):
                        continue

                    doc = await self._page_to_document(page)
                    if doc:
                        documents.append(doc)
                        page_count += 1

                has_more = results.get("has_more", False)
                start_cursor = results.get("next_cursor")

                # Safety limit
                if page_count >= 1000:
                    print(f"[Notion] Reached page limit (1000)")
                    break

            # Update sync stats
            self.sync_stats = {
                "documents_synced": len(documents),
                "workspace": self.workspace_name,
                "sync_time": datetime.now(timezone.utc).isoformat()
            }
            self.config.last_sync = datetime.now(timezone.utc)
            self.status = ConnectorStatus.CONNECTED

            print(f"[Notion] Sync complete: {len(documents)} documents")

        except Exception as e:
            self._set_error(f"Sync failed: {str(e)}")
            import traceback
            traceback.print_exc()

        return documents

    async def get_document(self, doc_id: str) -> Optional[Document]:
        """Retrieve a specific page by ID"""
        if not self.client:
            await self.connect()

        try:
            # Remove prefix if present
            page_id = doc_id.replace("notion_", "")
            page = self.client.pages.retrieve(page_id)
            return await self._page_to_document(page)
        except Exception as e:
            self._set_error(f"Failed to get document: {str(e)}")
            return None

    async def _page_to_document(self, page: Dict[str, Any]) -> Optional[Document]:
        """Convert Notion page to Document object"""
        try:
            page_id = page["id"]
            properties = page.get("properties", {})

            # Extract title
            title = self._extract_title(properties)

            # Get page content via blocks
            content = await self._get_page_content(page_id)

            # Skip empty pages
            if not content.strip() and not title:
                return None

            # Determine parent info
            parent = page.get("parent", {})
            parent_type = parent.get("type", "")
            parent_info = ""

            if parent_type == "database_id":
                # Get database name
                try:
                    db = self.client.databases.retrieve(parent["database_id"])
                    db_title = db.get("title", [{}])
                    if db_title:
                        parent_info = db_title[0].get("plain_text", "Database")
                except:
                    parent_info = "Database"
            elif parent_type == "page_id":
                parent_info = "Subpage"
            elif parent_type == "workspace":
                parent_info = "Workspace"

            # Build metadata
            created_time = page.get("created_time", "")
            last_edited = page.get("last_edited_time", "")

            metadata = {
                "page_id": page_id,
                "parent_type": parent_type,
                "parent_info": parent_info,
                "url": page.get("url", ""),
                "created_by": page.get("created_by", {}).get("id", ""),
                "last_edited_by": page.get("last_edited_by", {}).get("id", ""),
                "archived": page.get("archived", False),
                "workspace": self.workspace_name
            }

            # Extract additional properties as metadata
            for prop_name, prop_value in properties.items():
                if prop_name.lower() != "title" and prop_name.lower() != "name":
                    extracted = self._extract_property_value(prop_value)
                    if extracted:
                        metadata[f"prop_{prop_name}"] = extracted

            # Parse timestamps
            timestamp = None
            if created_time:
                timestamp = datetime.fromisoformat(created_time.replace("Z", "+00:00"))

            return Document(
                doc_id=f"notion_{page_id}",
                source="notion",
                content=content,
                title=title or "Untitled",
                metadata=metadata,
                timestamp=timestamp,
                author=self.workspace_name,
                url=page.get("url"),
                doc_type="document"
            )

        except Exception as e:
            print(f"[Notion] Error converting page: {e}")
            return None

    def _extract_title(self, properties: Dict) -> str:
        """Extract title from page properties"""
        # Try common title property names
        for prop_name in ["title", "Title", "Name", "name"]:
            if prop_name in properties:
                prop = properties[prop_name]
                if prop.get("type") == "title":
                    title_array = prop.get("title", [])
                    return "".join([t.get("plain_text", "") for t in title_array])

        # Fallback: find any title-type property
        for prop in properties.values():
            if prop.get("type") == "title":
                title_array = prop.get("title", [])
                return "".join([t.get("plain_text", "") for t in title_array])

        return ""

    def _extract_property_value(self, prop: Dict) -> Optional[str]:
        """Extract value from a Notion property"""
        prop_type = prop.get("type", "")

        if prop_type == "rich_text":
            texts = prop.get("rich_text", [])
            return "".join([t.get("plain_text", "") for t in texts]) or None

        elif prop_type == "number":
            return str(prop.get("number")) if prop.get("number") is not None else None

        elif prop_type == "select":
            select = prop.get("select")
            return select.get("name") if select else None

        elif prop_type == "multi_select":
            options = prop.get("multi_select", [])
            return ", ".join([o.get("name", "") for o in options]) or None

        elif prop_type == "date":
            date = prop.get("date")
            if date:
                start = date.get("start", "")
                end = date.get("end", "")
                return f"{start} - {end}" if end else start
            return None

        elif prop_type == "checkbox":
            return "Yes" if prop.get("checkbox") else "No"

        elif prop_type == "url":
            return prop.get("url")

        elif prop_type == "email":
            return prop.get("email")

        elif prop_type == "phone_number":
            return prop.get("phone_number")

        elif prop_type == "status":
            status = prop.get("status")
            return status.get("name") if status else None

        return None

    async def _get_page_content(self, page_id: str) -> str:
        """Fetch and concatenate all blocks from a page"""
        content_parts = []
        max_blocks = self.config.settings.get("max_blocks_per_page", 200)

        try:
            has_more = True
            start_cursor = None
            block_count = 0

            while has_more and block_count < max_blocks:
                params = {"block_id": page_id, "page_size": 100}
                if start_cursor:
                    params["start_cursor"] = start_cursor

                response = self.client.blocks.children.list(**params)

                for block in response.get("results", []):
                    text = self._extract_block_text(block)
                    if text:
                        content_parts.append(text)
                    block_count += 1

                    # Recursively get children if block has them
                    if block.get("has_children") and block_count < max_blocks:
                        child_content = await self._get_page_content(block["id"])
                        if child_content:
                            content_parts.append(child_content)

                has_more = response.get("has_more", False)
                start_cursor = response.get("next_cursor")

        except Exception as e:
            print(f"[Notion] Error fetching blocks: {e}")

        return "\n".join(content_parts)

    def _extract_block_text(self, block: Dict) -> str:
        """Extract text content from a Notion block"""
        block_type = block.get("type", "")
        block_data = block.get(block_type, {})

        # Text extraction helper
        def get_rich_text(data: Dict) -> str:
            texts = data.get("rich_text", [])
            return "".join([t.get("plain_text", "") for t in texts])

        if block_type == "paragraph":
            return get_rich_text(block_data)

        elif block_type == "heading_1":
            return f"# {get_rich_text(block_data)}"

        elif block_type == "heading_2":
            return f"## {get_rich_text(block_data)}"

        elif block_type == "heading_3":
            return f"### {get_rich_text(block_data)}"

        elif block_type == "bulleted_list_item":
            return f"- {get_rich_text(block_data)}"

        elif block_type == "numbered_list_item":
            return f"1. {get_rich_text(block_data)}"

        elif block_type == "to_do":
            checked = "x" if block_data.get("checked") else " "
            return f"- [{checked}] {get_rich_text(block_data)}"

        elif block_type == "toggle":
            return f"> {get_rich_text(block_data)}"

        elif block_type == "code":
            language = block_data.get("language", "text")
            code = get_rich_text(block_data)
            return f"```{language}\n{code}\n```"

        elif block_type == "quote":
            return f"> {get_rich_text(block_data)}"

        elif block_type == "callout":
            emoji = block_data.get("icon", {}).get("emoji", "")
            text = get_rich_text(block_data)
            return f"{emoji} {text}" if emoji else text

        elif block_type == "divider":
            return "---"

        elif block_type == "table_row":
            cells = block_data.get("cells", [])
            row_text = " | ".join([
                "".join([t.get("plain_text", "") for t in cell])
                for cell in cells
            ])
            return f"| {row_text} |"

        elif block_type == "bookmark":
            url = block_data.get("url", "")
            caption = get_rich_text(block_data)
            return f"[{caption or 'Bookmark'}]({url})" if url else ""

        elif block_type == "embed":
            return f"[Embedded: {block_data.get('url', '')}]"

        elif block_type == "image":
            img_type = block_data.get("type", "")
            if img_type == "external":
                return f"[Image: {block_data.get('external', {}).get('url', '')}]"
            elif img_type == "file":
                return f"[Image: {block_data.get('file', {}).get('url', '')}]"

        elif block_type == "video":
            return "[Video embedded]"

        elif block_type == "pdf":
            return "[PDF embedded]"

        elif block_type == "file":
            return "[File attached]"

        elif block_type == "equation":
            return f"$${block_data.get('expression', '')}$$"

        elif block_type == "table_of_contents":
            return "[Table of Contents]"

        elif block_type == "breadcrumb":
            return ""  # Skip breadcrumbs

        elif block_type == "column_list":
            return ""  # Content will be in children

        elif block_type == "column":
            return ""  # Content will be in children

        elif block_type == "synced_block":
            return ""  # Content will be in children

        return ""

    @classmethod
    def get_auth_url(cls, redirect_uri: str, state: str) -> str:
        """Generate Notion OAuth authorization URL"""
        client_id = os.getenv("NOTION_CLIENT_ID", "")

        # Notion OAuth URL
        auth_url = (
            f"https://api.notion.com/v1/oauth/authorize"
            f"?client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&response_type=code"
            f"&owner=user"
            f"&state={state}"
        )

        return auth_url

    @classmethod
    async def exchange_code(cls, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        import requests
        import base64

        client_id = os.getenv("NOTION_CLIENT_ID", "")
        client_secret = os.getenv("NOTION_CLIENT_SECRET", "")

        # Notion uses Basic auth for token exchange
        credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

        response = requests.post(
            "https://api.notion.com/v1/oauth/token",
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/json"
            },
            json={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri
            }
        )

        data = response.json()

        if "error" in data:
            raise Exception(f"OAuth failed: {data.get('error_description', data['error'])}")

        return {
            "access_token": data.get("access_token"),
            "workspace_id": data.get("workspace_id"),
            "workspace_name": data.get("workspace_name"),
            "bot_id": data.get("bot_id")
        }
```

### 2.3 Add Notion Routes

**File:** `backend/api/integration_routes.py` (add to existing file)

```python
# ============================================================================
# NOTION INTEGRATION
# ============================================================================

@integration_bp.route('/notion/auth', methods=['GET'])
@require_auth
def notion_auth():
    """Initiate Notion OAuth flow"""
    try:
        from connectors.notion_connector import NotionConnector, NOTION_AVAILABLE

        if not NOTION_AVAILABLE:
            return jsonify({
                "success": False,
                "error": "Notion SDK not installed"
            }), 500

        redirect_uri = os.getenv(
            "NOTION_REDIRECT_URI",
            f"{os.getenv('BACKEND_URL', 'http://localhost:5003')}/api/integrations/notion/callback"
        )

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

    except Exception as e:
        print(f"[Notion] Auth error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@integration_bp.route('/notion/callback', methods=['GET'])
def notion_callback():
    """Handle Notion OAuth callback"""
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

    try:
        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')

        if error:
            return redirect(f"{FRONTEND_URL}/integrations?error=notion_{error}")

        if not code or not state:
            return redirect(f"{FRONTEND_URL}/integrations?error=notion_missing_params")

        # Verify state
        state_data, error_msg = verify_oauth_state(state)
        if error_msg:
            return redirect(f"{FRONTEND_URL}/integrations?error=notion_invalid_state")

        if state_data.get("connector_type") != "notion":
            return redirect(f"{FRONTEND_URL}/integrations?error=notion_wrong_connector")

        from connectors.notion_connector import NotionConnector
        import asyncio

        # Exchange code for token
        redirect_uri = state_data.get("data", {}).get("redirect_uri")
        if not redirect_uri:
            redirect_uri = os.getenv("NOTION_REDIRECT_URI")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        tokens = loop.run_until_complete(NotionConnector.exchange_code(code, redirect_uri))
        loop.close()

        # Save to database
        db = get_db()
        try:
            from database.models import Connector, ConnectorType, ConnectorStatus

            connector = db.query(Connector).filter(
                Connector.tenant_id == state_data['tenant_id'],
                Connector.connector_type == ConnectorType.NOTION
            ).first()

            is_first = connector is None
            workspace_name = tokens.get('workspace_name', 'Notion')

            if connector:
                connector.access_token = tokens["access_token"]
                connector.status = ConnectorStatus.CONNECTED
                connector.is_active = True
                connector.error_message = None
                connector.name = f"Notion ({workspace_name})"
            else:
                connector = Connector(
                    tenant_id=state_data['tenant_id'],
                    user_id=state_data['user_id'],
                    connector_type=ConnectorType.NOTION,
                    name=f"Notion ({workspace_name})",
                    status=ConnectorStatus.CONNECTED,
                    access_token=tokens["access_token"],
                    settings={}
                )
                db.add(connector)

            db.commit()
            connector_id = connector.id

            # Auto-sync on first connection
            if is_first:
                def run_notion_sync():
                    _run_connector_sync(
                        connector_id=connector_id,
                        connector_type="notion",
                        since=None,
                        tenant_id=state_data['tenant_id'],
                        user_id=state_data['user_id'],
                        full_sync=True
                    )

                spawn_background_task(run_notion_sync)

            return redirect(f"{FRONTEND_URL}/integrations?success=notion")

        finally:
            db.close()

    except Exception as e:
        print(f"[Notion] Callback error: {e}")
        import traceback
        traceback.print_exc()
        return redirect(f"{FRONTEND_URL}/integrations?error=notion_exchange_failed")


@integration_bp.route('/notion/sync', methods=['POST'])
@require_auth
def notion_sync():
    """Trigger manual Notion sync"""
    db = get_db()
    try:
        from database.models import Connector, ConnectorType, ConnectorStatus

        connector = db.query(Connector).filter(
            Connector.tenant_id == g.tenant_id,
            Connector.connector_type == ConnectorType.NOTION
        ).first()

        if not connector:
            return jsonify({"success": False, "error": "Notion not connected"}), 404

        if connector.status == ConnectorStatus.SYNCING:
            return jsonify({"success": False, "error": "Sync already in progress"}), 409

        data = request.get_json() or {}
        full_sync = data.get('full_sync', False)
        since = None if full_sync else connector.last_sync_at

        # Generate sync ID for progress tracking
        sync_id = f"notion_{connector.id}_{datetime.now(timezone.utc).timestamp()}"

        def run_sync():
            _run_connector_sync(
                connector_id=connector.id,
                connector_type="notion",
                since=since,
                tenant_id=g.tenant_id,
                user_id=g.user_id,
                full_sync=full_sync,
                sync_id=sync_id
            )

        spawn_background_task(run_sync)

        return jsonify({
            "success": True,
            "message": "Sync started",
            "sync_id": sync_id
        })

    finally:
        db.close()


@integration_bp.route('/notion/disconnect', methods=['POST'])
@require_auth
def notion_disconnect():
    """Disconnect Notion integration"""
    db = get_db()
    try:
        from database.models import Connector, ConnectorType, ConnectorStatus

        connector = db.query(Connector).filter(
            Connector.tenant_id == g.tenant_id,
            Connector.connector_type == ConnectorType.NOTION
        ).first()

        if not connector:
            return jsonify({"success": False, "error": "Notion not connected"}), 404

        # Clear tokens and mark as disconnected
        connector.access_token = None
        connector.refresh_token = None
        connector.status = ConnectorStatus.DISCONNECTED
        connector.is_active = False
        db.commit()

        return jsonify({"success": True, "message": "Notion disconnected"})

    finally:
        db.close()
```

---

## Phase 3: Zotero Integration

### 3.1 Overview

| Aspect | Details |
|--------|---------|
| Auth Type | OAuth 1.0a (legacy) OR API Key (simpler) |
| API | Zotero Web API v3 |
| SDK | `pyzotero` |
| Sync Content | Library items, Collections, PDF annotations |
| Document Type | `research_paper` |

**Note:** Zotero uses OAuth 1.0a which is more complex. We'll support both OAuth and API key for flexibility.

### 3.2 Create Connector

**File:** `backend/connectors/zotero_connector.py`

```python
"""
Zotero Connector for 2nd Brain
Syncs research papers, citations, and annotations from Zotero libraries
"""

import os
import asyncio
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from urllib.parse import urlencode

from connectors.base_connector import (
    BaseConnector,
    ConnectorConfig,
    ConnectorStatus,
    Document
)

try:
    from pyzotero import zotero
    ZOTERO_AVAILABLE = True
except ImportError:
    ZOTERO_AVAILABLE = False


class ZoteroConnector(BaseConnector):
    """Connector for Zotero research libraries"""

    CONNECTOR_TYPE = "zotero"
    REQUIRED_CREDENTIALS = ["api_key", "user_id"]  # or library_id for groups
    OPTIONAL_SETTINGS = {
        "library_type": "user",       # "user" or "group"
        "collection_ids": [],         # Specific collections to sync (empty = all)
        "include_attachments": True,  # Include PDF text extraction
        "include_notes": True,        # Include item notes
        "include_tags": True,         # Include tags in metadata
        "max_items": 1000            # Maximum items to sync
    }

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.zot: Optional[zotero.Zotero] = None
        self.library_name: str = ""

    async def connect(self) -> bool:
        """Establish connection to Zotero API"""
        if not ZOTERO_AVAILABLE:
            self._set_error("pyzotero not installed. Run: pip install pyzotero")
            return False

        try:
            self.status = ConnectorStatus.CONNECTING

            api_key = self.config.credentials.get("api_key")
            library_id = self.config.credentials.get("user_id") or self.config.credentials.get("library_id")
            library_type = self.config.settings.get("library_type", "user")

            if not api_key or not library_id:
                self._set_error("Missing api_key or library_id")
                return False

            # Initialize Zotero client
            self.zot = zotero.Zotero(library_id, library_type, api_key)

            # Test connection by getting key info
            key_info = self.zot.key_info()
            self.library_name = key_info.get("username", f"Zotero {library_type}")

            self.status = ConnectorStatus.CONNECTED
            self._clear_error()
            print(f"[Zotero] Connected to library: {self.library_name}")
            return True

        except Exception as e:
            self._set_error(f"Connection failed: {str(e)}")
            return False

    async def disconnect(self) -> bool:
        """Disconnect from Zotero"""
        self.zot = None
        self.status = ConnectorStatus.DISCONNECTED
        return True

    async def test_connection(self) -> bool:
        """Verify connection is still valid"""
        if not self.zot:
            return False
        try:
            self.zot.key_info()
            return True
        except Exception:
            return False

    async def sync(self, since: Optional[datetime] = None) -> List[Document]:
        """
        Sync items from Zotero library

        Args:
            since: Only sync items modified after this time

        Returns:
            List of Document objects
        """
        if not self.zot:
            connected = await self.connect()
            if not connected:
                return []

        self.status = ConnectorStatus.SYNCING
        documents = []

        try:
            max_items = self.config.settings.get("max_items", 1000)
            collection_ids = self.config.settings.get("collection_ids", [])

            print(f"[Zotero] Starting sync (since={since}, collections={collection_ids})")

            # Build query params
            params = {
                "limit": min(100, max_items),
                "sort": "dateModified",
                "direction": "desc"
            }

            if since:
                # Zotero uses version numbers, not timestamps directly
                # We'll filter client-side for simplicity
                pass

            items = []

            if collection_ids:
                # Sync specific collections
                for coll_id in collection_ids:
                    coll_items = self.zot.collection_items(coll_id, **params)
                    items.extend(coll_items)
            else:
                # Sync all items
                items = self.zot.items(**params)

            # Process items
            for item in items[:max_items]:
                # Skip attachments (processed separately)
                item_type = item.get("data", {}).get("itemType", "")
                if item_type == "attachment":
                    continue

                # Filter by date if incremental
                if since:
                    modified = item.get("data", {}).get("dateModified", "")
                    if modified:
                        try:
                            mod_dt = datetime.fromisoformat(modified.replace("Z", "+00:00"))
                            if mod_dt < since:
                                continue
                        except:
                            pass

                doc = await self._item_to_document(item)
                if doc:
                    documents.append(doc)

            # Update sync stats
            self.sync_stats = {
                "documents_synced": len(documents),
                "library": self.library_name,
                "sync_time": datetime.now(timezone.utc).isoformat()
            }
            self.config.last_sync = datetime.now(timezone.utc)
            self.status = ConnectorStatus.CONNECTED

            print(f"[Zotero] Sync complete: {len(documents)} items")

        except Exception as e:
            self._set_error(f"Sync failed: {str(e)}")
            import traceback
            traceback.print_exc()

        return documents

    async def get_document(self, doc_id: str) -> Optional[Document]:
        """Retrieve a specific item by key"""
        if not self.zot:
            await self.connect()

        try:
            item_key = doc_id.replace("zotero_", "")
            item = self.zot.item(item_key)
            return await self._item_to_document(item)
        except Exception as e:
            self._set_error(f"Failed to get document: {str(e)}")
            return None

    async def _item_to_document(self, item: Dict[str, Any]) -> Optional[Document]:
        """Convert Zotero item to Document object"""
        try:
            data = item.get("data", {})
            item_key = data.get("key", "")
            item_type = data.get("itemType", "")

            # Build title
            title = data.get("title", "")
            if not title:
                title = data.get("name", "") or data.get("subject", "") or "Untitled"

            # Build content from abstract and notes
            content_parts = []

            # Add abstract
            abstract = data.get("abstractNote", "")
            if abstract:
                content_parts.append(f"Abstract:\n{abstract}")

            # Add notes if enabled
            if self.config.settings.get("include_notes", True):
                try:
                    children = self.zot.children(item_key)
                    for child in children:
                        child_data = child.get("data", {})
                        if child_data.get("itemType") == "note":
                            note_text = child_data.get("note", "")
                            if note_text:
                                # Strip HTML tags
                                import re
                                note_clean = re.sub('<[^<]+?>', '', note_text)
                                content_parts.append(f"Note:\n{note_clean}")
                except:
                    pass

            # Add PDF text if available and enabled
            if self.config.settings.get("include_attachments", True):
                try:
                    children = self.zot.children(item_key)
                    for child in children:
                        child_data = child.get("data", {})
                        if child_data.get("itemType") == "attachment":
                            content_type = child_data.get("contentType", "")
                            if "pdf" in content_type.lower():
                                # Note: Full PDF text extraction would require downloading
                                # For now, just note that PDF is attached
                                filename = child_data.get("filename", "document.pdf")
                                content_parts.append(f"[PDF Attached: {filename}]")
                except:
                    pass

            content = "\n\n".join(content_parts)

            # Build metadata
            metadata = {
                "item_key": item_key,
                "item_type": item_type,
                "library": self.library_name
            }

            # Add bibliographic fields
            for field in ["creators", "date", "publisher", "publicationTitle",
                         "volume", "issue", "pages", "DOI", "ISBN", "ISSN",
                         "url", "language", "rights"]:
                if data.get(field):
                    metadata[field] = data[field]

            # Format creators
            creators = data.get("creators", [])
            author_names = []
            for creator in creators:
                name = f"{creator.get('firstName', '')} {creator.get('lastName', '')}".strip()
                if not name:
                    name = creator.get("name", "")
                if name:
                    author_names.append(name)

            author = ", ".join(author_names) if author_names else None

            # Add tags if enabled
            if self.config.settings.get("include_tags", True):
                tags = [t.get("tag", "") for t in data.get("tags", [])]
                if tags:
                    metadata["tags"] = tags

            # Add collections
            collections = data.get("collections", [])
            if collections:
                metadata["collection_ids"] = collections

            # Parse date
            timestamp = None
            date_str = data.get("date", "") or data.get("dateModified", "")
            if date_str:
                try:
                    # Zotero dates can be various formats
                    if "T" in date_str:
                        timestamp = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    else:
                        # Try parsing year-only or year-month
                        from dateutil.parser import parse
                        timestamp = parse(date_str)
                except:
                    pass

            # Get URL
            url = data.get("url", "") or data.get("DOI", "")
            if url and url.startswith("10."):
                url = f"https://doi.org/{url}"

            return Document(
                doc_id=f"zotero_{item_key}",
                source="zotero",
                content=content,
                title=title,
                metadata=metadata,
                timestamp=timestamp,
                author=author,
                url=url,
                doc_type="research_paper"
            )

        except Exception as e:
            print(f"[Zotero] Error converting item: {e}")
            return None

    @classmethod
    def get_auth_url(cls, redirect_uri: str, state: str) -> str:
        """
        Generate Zotero OAuth 1.0a authorization URL
        Note: Zotero uses OAuth 1.0a which requires a request token first
        For simplicity, we'll use API key authentication instead
        """
        # For OAuth 1.0a, you would need to:
        # 1. Get request token from /oauth/request
        # 2. Redirect user to /oauth/authorize
        # 3. Exchange for access token at /oauth/access

        # Simpler approach: Direct user to get API key
        return f"https://www.zotero.org/settings/keys/new?state={state}"

    @classmethod
    async def exchange_code(cls, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        For Zotero, users provide API key directly (not OAuth code exchange)
        """
        # In API key mode, the "code" is actually the API key
        return {
            "api_key": code
        }
```

### 3.3 Add Zotero Routes

**File:** `backend/api/integration_routes.py` (add to existing file)

```python
# ============================================================================
# ZOTERO INTEGRATION (API Key based - simpler than OAuth 1.0a)
# ============================================================================

@integration_bp.route('/zotero/configure', methods=['POST'])
@require_auth
def zotero_configure():
    """Configure Zotero connection with API key"""
    try:
        data = request.get_json() or {}

        api_key = data.get("api_key", "").strip()
        user_id = data.get("user_id", "").strip()  # Zotero user ID (numeric)
        library_type = data.get("library_type", "user")  # "user" or "group"
        collection_ids = data.get("collection_ids", [])

        if not api_key:
            return jsonify({"success": False, "error": "API key is required"}), 400

        if not user_id:
            return jsonify({"success": False, "error": "User/Library ID is required"}), 400

        from connectors.zotero_connector import ZoteroConnector, ZOTERO_AVAILABLE

        if not ZOTERO_AVAILABLE:
            return jsonify({"success": False, "error": "pyzotero not installed"}), 500

        # Test connection
        from connectors.base_connector import ConnectorConfig
        test_config = ConnectorConfig(
            connector_type="zotero",
            user_id=g.user_id,
            credentials={"api_key": api_key, "user_id": user_id},
            settings={"library_type": library_type}
        )

        connector_instance = ZoteroConnector(test_config)

        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        connected = loop.run_until_complete(connector_instance.connect())
        loop.close()

        if not connected:
            return jsonify({
                "success": False,
                "error": f"Connection failed: {connector_instance.last_error}"
            }), 400

        # Save to database
        db = get_db()
        try:
            from database.models import Connector, ConnectorType, ConnectorStatus

            connector = db.query(Connector).filter(
                Connector.tenant_id == g.tenant_id,
                Connector.connector_type == ConnectorType.ZOTERO
            ).first()

            is_first = connector is None

            settings = {
                "library_type": library_type,
                "collection_ids": collection_ids,
                "include_attachments": data.get("include_attachments", True),
                "include_notes": data.get("include_notes", True),
                "include_tags": data.get("include_tags", True)
            }

            if connector:
                connector.access_token = api_key
                connector.settings = {**connector.settings, **settings, "user_id": user_id}
                connector.status = ConnectorStatus.CONNECTED
                connector.is_active = True
                connector.error_message = None
                connector.name = f"Zotero ({connector_instance.library_name})"
            else:
                connector = Connector(
                    tenant_id=g.tenant_id,
                    user_id=g.user_id,
                    connector_type=ConnectorType.ZOTERO,
                    name=f"Zotero ({connector_instance.library_name})",
                    status=ConnectorStatus.CONNECTED,
                    access_token=api_key,
                    settings={**settings, "user_id": user_id}
                )
                db.add(connector)

            db.commit()
            connector_id = connector.id

            # Auto-sync
            if is_first or data.get("auto_sync", True):
                def run_zotero_sync():
                    _run_connector_sync(
                        connector_id=connector_id,
                        connector_type="zotero",
                        since=None,
                        tenant_id=g.tenant_id,
                        user_id=g.user_id,
                        full_sync=True
                    )

                spawn_background_task(run_zotero_sync)

            return jsonify({
                "success": True,
                "connector_id": connector_id,
                "library_name": connector_instance.library_name
            })

        finally:
            db.close()

    except Exception as e:
        print(f"[Zotero] Configure error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@integration_bp.route('/zotero/status', methods=['GET'])
@require_auth
def zotero_status():
    """Get Zotero connection status"""
    db = get_db()
    try:
        from database.models import Connector, ConnectorType

        connector = db.query(Connector).filter(
            Connector.tenant_id == g.tenant_id,
            Connector.connector_type == ConnectorType.ZOTERO
        ).first()

        if not connector:
            return jsonify({
                "success": True,
                "status": {
                    "connected": False
                }
            })

        return jsonify({
            "success": True,
            "status": {
                "connected": connector.status.value == "connected",
                "status": connector.status.value,
                "name": connector.name,
                "last_sync_at": connector.last_sync_at.isoformat() if connector.last_sync_at else None,
                "total_items_synced": connector.total_items_synced,
                "error_message": connector.error_message,
                "settings": connector.settings
            }
        })

    finally:
        db.close()


@integration_bp.route('/zotero/sync', methods=['POST'])
@require_auth
def zotero_sync():
    """Trigger manual Zotero sync"""
    db = get_db()
    try:
        from database.models import Connector, ConnectorType, ConnectorStatus

        connector = db.query(Connector).filter(
            Connector.tenant_id == g.tenant_id,
            Connector.connector_type == ConnectorType.ZOTERO
        ).first()

        if not connector:
            return jsonify({"success": False, "error": "Zotero not connected"}), 404

        if connector.status == ConnectorStatus.SYNCING:
            return jsonify({"success": False, "error": "Sync already in progress"}), 409

        data = request.get_json() or {}
        full_sync = data.get('full_sync', False)
        since = None if full_sync else connector.last_sync_at

        sync_id = f"zotero_{connector.id}_{datetime.now(timezone.utc).timestamp()}"

        def run_sync():
            _run_connector_sync(
                connector_id=connector.id,
                connector_type="zotero",
                since=since,
                tenant_id=g.tenant_id,
                user_id=g.user_id,
                full_sync=full_sync,
                sync_id=sync_id
            )

        spawn_background_task(run_sync)

        return jsonify({
            "success": True,
            "message": "Sync started",
            "sync_id": sync_id
        })

    finally:
        db.close()


@integration_bp.route('/zotero/disconnect', methods=['POST'])
@require_auth
def zotero_disconnect():
    """Disconnect Zotero integration"""
    db = get_db()
    try:
        from database.models import Connector, ConnectorType, ConnectorStatus

        connector = db.query(Connector).filter(
            Connector.tenant_id == g.tenant_id,
            Connector.connector_type == ConnectorType.ZOTERO
        ).first()

        if not connector:
            return jsonify({"success": False, "error": "Zotero not connected"}), 404

        connector.access_token = None
        connector.status = ConnectorStatus.DISCONNECTED
        connector.is_active = False
        db.commit()

        return jsonify({"success": True, "message": "Zotero disconnected"})

    finally:
        db.close()


@integration_bp.route('/zotero/collections', methods=['GET'])
@require_auth
def zotero_collections():
    """Get list of Zotero collections for selection"""
    db = get_db()
    try:
        from database.models import Connector, ConnectorType

        connector = db.query(Connector).filter(
            Connector.tenant_id == g.tenant_id,
            Connector.connector_type == ConnectorType.ZOTERO
        ).first()

        if not connector or not connector.access_token:
            return jsonify({"success": False, "error": "Zotero not connected"}), 404

        from pyzotero import zotero

        user_id = connector.settings.get("user_id")
        library_type = connector.settings.get("library_type", "user")

        zot = zotero.Zotero(user_id, library_type, connector.access_token)
        collections = zot.collections()

        result = []
        for coll in collections:
            data = coll.get("data", {})
            result.append({
                "key": data.get("key"),
                "name": data.get("name"),
                "parent": data.get("parentCollection"),
                "item_count": coll.get("meta", {}).get("numItems", 0)
            })

        return jsonify({
            "success": True,
            "collections": result
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

    finally:
        db.close()
```

---

## Phase 4: Google Drive Integration

### 4.1 Overview

| Aspect | Details |
|--------|---------|
| Auth Type | OAuth 2.0 (reuses Google OAuth app from Gmail) |
| API | Google Drive API v3 |
| SDK | `google-api-python-client` (already installed) |
| Sync Content | Documents, Spreadsheets, PDFs, Text files |
| Document Type | `file` |

### 4.2 Create Connector

**File:** `backend/connectors/gdrive_connector.py`

```python
"""
Google Drive Connector for 2nd Brain
Syncs documents and files from Google Drive
"""

import os
import asyncio
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import io

from connectors.base_connector import (
    BaseConnector,
    ConnectorConfig,
    ConnectorStatus,
    Document
)

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    GDRIVE_AVAILABLE = True
except ImportError:
    GDRIVE_AVAILABLE = False


# Google Drive scopes
GDRIVE_SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/drive.metadata.readonly'
]

# Supported MIME types for content extraction
EXTRACTABLE_TYPES = {
    'application/vnd.google-apps.document': 'text/plain',      # Google Docs
    'application/vnd.google-apps.spreadsheet': 'text/csv',     # Google Sheets
    'application/vnd.google-apps.presentation': 'text/plain',  # Google Slides
    'application/pdf': None,                                    # PDF (needs parsing)
    'text/plain': None,
    'text/markdown': None,
    'text/html': None,
    'application/json': None,
    'application/rtf': None,
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': None,  # docx
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': None,        # xlsx
}


class GDriveConnector(BaseConnector):
    """Connector for Google Drive"""

    CONNECTOR_TYPE = "gdrive"
    REQUIRED_CREDENTIALS = ["access_token", "refresh_token"]
    OPTIONAL_SETTINGS = {
        "folder_ids": [],              # Specific folders to sync (empty = all)
        "include_shared": True,        # Include shared files
        "include_trashed": False,      # Include trashed files
        "max_file_size_mb": 25,        # Skip files larger than this
        "file_types": [],              # Filter by extension (empty = all supported)
        "max_files": 500               # Maximum files to sync
    }

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.service = None
        self.credentials: Optional[Credentials] = None
        self.user_email: str = ""

    async def connect(self) -> bool:
        """Establish connection to Google Drive API"""
        if not GDRIVE_AVAILABLE:
            self._set_error("Google API SDK not installed")
            return False

        try:
            self.status = ConnectorStatus.CONNECTING

            access_token = self.config.credentials.get("access_token")
            refresh_token = self.config.credentials.get("refresh_token")

            if not access_token:
                self._set_error("Missing access_token")
                return False

            # Create credentials object
            self.credentials = Credentials(
                token=access_token,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=os.getenv("GOOGLE_CLIENT_ID"),
                client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
                scopes=GDRIVE_SCOPES
            )

            # Build service
            self.service = build('drive', 'v3', credentials=self.credentials)

            # Test connection and get user info
            about = self.service.about().get(fields="user").execute()
            self.user_email = about.get("user", {}).get("emailAddress", "")

            self.status = ConnectorStatus.CONNECTED
            self._clear_error()
            print(f"[GDrive] Connected as: {self.user_email}")
            return True

        except Exception as e:
            self._set_error(f"Connection failed: {str(e)}")
            return False

    async def disconnect(self) -> bool:
        """Disconnect from Google Drive"""
        self.service = None
        self.credentials = None
        self.status = ConnectorStatus.DISCONNECTED
        return True

    async def test_connection(self) -> bool:
        """Verify connection is still valid"""
        if not self.service:
            return False
        try:
            self.service.about().get(fields="user").execute()
            return True
        except Exception:
            return False

    async def refresh_tokens(self) -> bool:
        """Refresh OAuth tokens"""
        if not self.credentials or not self.credentials.refresh_token:
            return False

        try:
            from google.auth.transport.requests import Request
            self.credentials.refresh(Request())

            # Update stored tokens
            self.config.credentials["access_token"] = self.credentials.token

            return True
        except Exception as e:
            self._set_error(f"Token refresh failed: {str(e)}")
            return False

    async def sync(self, since: Optional[datetime] = None) -> List[Document]:
        """
        Sync files from Google Drive

        Args:
            since: Only sync files modified after this time

        Returns:
            List of Document objects
        """
        if not self.service:
            connected = await self.connect()
            if not connected:
                return []

        self.status = ConnectorStatus.SYNCING
        documents = []

        try:
            max_files = self.config.settings.get("max_files", 500)
            folder_ids = self.config.settings.get("folder_ids", [])
            include_shared = self.config.settings.get("include_shared", True)
            include_trashed = self.config.settings.get("include_trashed", False)
            max_size = self.config.settings.get("max_file_size_mb", 25) * 1024 * 1024

            print(f"[GDrive] Starting sync (since={since}, folders={folder_ids})")

            # Build query
            query_parts = []

            # Filter by supported MIME types
            mime_queries = [f"mimeType='{mt}'" for mt in EXTRACTABLE_TYPES.keys()]
            query_parts.append(f"({' or '.join(mime_queries)})")

            # Filter trashed
            if not include_trashed:
                query_parts.append("trashed=false")

            # Filter by modified time
            if since:
                since_str = since.strftime("%Y-%m-%dT%H:%M:%S")
                query_parts.append(f"modifiedTime > '{since_str}'")

            # Filter by folders
            if folder_ids:
                folder_queries = [f"'{fid}' in parents" for fid in folder_ids]
                query_parts.append(f"({' or '.join(folder_queries)})")

            query = " and ".join(query_parts)

            # Fetch files
            page_token = None
            file_count = 0

            while file_count < max_files:
                response = self.service.files().list(
                    q=query,
                    spaces='drive',
                    fields='nextPageToken, files(id, name, mimeType, size, modifiedTime, createdTime, owners, webViewLink, parents, description)',
                    pageToken=page_token,
                    pageSize=min(100, max_files - file_count),
                    includeItemsFromAllDrives=include_shared,
                    supportsAllDrives=True
                ).execute()

                files = response.get('files', [])

                for file in files:
                    # Skip large files
                    size = int(file.get('size', 0) or 0)
                    if size > max_size:
                        print(f"[GDrive] Skipping large file: {file['name']} ({size} bytes)")
                        continue

                    doc = await self._file_to_document(file)
                    if doc:
                        documents.append(doc)
                        file_count += 1

                        if file_count >= max_files:
                            break

                page_token = response.get('nextPageToken')
                if not page_token:
                    break

            # Update sync stats
            self.sync_stats = {
                "documents_synced": len(documents),
                "user": self.user_email,
                "sync_time": datetime.now(timezone.utc).isoformat()
            }
            self.config.last_sync = datetime.now(timezone.utc)
            self.status = ConnectorStatus.CONNECTED

            print(f"[GDrive] Sync complete: {len(documents)} files")

        except Exception as e:
            self._set_error(f"Sync failed: {str(e)}")
            import traceback
            traceback.print_exc()

        return documents

    async def get_document(self, doc_id: str) -> Optional[Document]:
        """Retrieve a specific file by ID"""
        if not self.service:
            await self.connect()

        try:
            file_id = doc_id.replace("gdrive_", "")
            file = self.service.files().get(
                fileId=file_id,
                fields='id, name, mimeType, size, modifiedTime, createdTime, owners, webViewLink, parents, description'
            ).execute()
            return await self._file_to_document(file)
        except Exception as e:
            self._set_error(f"Failed to get document: {str(e)}")
            return None

    async def _file_to_document(self, file: Dict[str, Any]) -> Optional[Document]:
        """Convert Google Drive file to Document object"""
        try:
            file_id = file['id']
            name = file['name']
            mime_type = file['mimeType']

            # Extract content
            content = await self._extract_content(file_id, mime_type, name)

            if not content:
                print(f"[GDrive] No content extracted for: {name}")
                return None

            # Build metadata
            owners = file.get('owners', [])
            owner_names = [o.get('displayName', o.get('emailAddress', '')) for o in owners]

            metadata = {
                "file_id": file_id,
                "mime_type": mime_type,
                "size": file.get('size'),
                "owners": owner_names,
                "parents": file.get('parents', []),
                "description": file.get('description', ''),
                "user": self.user_email
            }

            # Parse timestamps
            modified = file.get('modifiedTime', '')
            created = file.get('createdTime', '')

            timestamp = None
            if modified:
                timestamp = datetime.fromisoformat(modified.replace('Z', '+00:00'))
            elif created:
                timestamp = datetime.fromisoformat(created.replace('Z', '+00:00'))

            return Document(
                doc_id=f"gdrive_{file_id}",
                source="gdrive",
                content=content,
                title=name,
                metadata=metadata,
                timestamp=timestamp,
                author=owner_names[0] if owner_names else None,
                url=file.get('webViewLink'),
                doc_type="file"
            )

        except Exception as e:
            print(f"[GDrive] Error converting file: {e}")
            return None

    async def _extract_content(self, file_id: str, mime_type: str, filename: str) -> Optional[str]:
        """Extract text content from file"""
        try:
            # Google Workspace files - export as text
            if mime_type.startswith('application/vnd.google-apps.'):
                export_type = EXTRACTABLE_TYPES.get(mime_type)
                if export_type:
                    response = self.service.files().export(
                        fileId=file_id,
                        mimeType=export_type
                    ).execute()

                    if isinstance(response, bytes):
                        return response.decode('utf-8', errors='ignore')
                    return str(response)
                return None

            # Regular files - download and extract
            request = self.service.files().get_media(fileId=file_id)
            file_buffer = io.BytesIO()
            downloader = MediaIoBaseDownload(file_buffer, request)

            done = False
            while not done:
                _, done = downloader.next_chunk()

            file_content = file_buffer.getvalue()

            # Handle based on type
            if mime_type in ['text/plain', 'text/markdown', 'application/json']:
                return file_content.decode('utf-8', errors='ignore')

            elif mime_type == 'text/html':
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(file_content, 'html.parser')
                return soup.get_text(separator='\n')

            elif mime_type == 'application/pdf':
                # Use LlamaParse if available, otherwise skip
                try:
                    from parsers.llamaparse_parser import LlamaParseParser
                    parser = LlamaParseParser()
                    return parser.parse_bytes(file_content, filename)
                except:
                    # Fallback: just note it's a PDF
                    return f"[PDF document: {filename}]"

            elif 'word' in mime_type or 'document' in mime_type:
                try:
                    import docx
                    doc = docx.Document(io.BytesIO(file_content))
                    return '\n'.join([p.text for p in doc.paragraphs])
                except:
                    return None

            elif 'spreadsheet' in mime_type or 'excel' in mime_type:
                try:
                    import pandas as pd
                    df = pd.read_excel(io.BytesIO(file_content))
                    return df.to_string()
                except:
                    return None

            return None

        except Exception as e:
            print(f"[GDrive] Content extraction error: {e}")
            return None

    @classmethod
    def get_auth_url(cls, redirect_uri: str, state: str) -> str:
        """Generate Google OAuth authorization URL for Drive access"""
        client_id = os.getenv("GOOGLE_CLIENT_ID", "")

        params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'scope': ' '.join(GDRIVE_SCOPES),
            'response_type': 'code',
            'access_type': 'offline',
            'prompt': 'consent',
            'state': state
        }

        from urllib.parse import urlencode
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

    @classmethod
    async def exchange_code(cls, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for tokens"""
        import requests

        response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                'client_id': os.getenv("GOOGLE_CLIENT_ID"),
                'client_secret': os.getenv("GOOGLE_CLIENT_SECRET"),
                'code': code,
                'grant_type': 'authorization_code',
                'redirect_uri': redirect_uri
            }
        )

        data = response.json()

        if 'error' in data:
            raise Exception(f"OAuth failed: {data.get('error_description', data['error'])}")

        return {
            'access_token': data['access_token'],
            'refresh_token': data.get('refresh_token'),
            'expires_in': data.get('expires_in'),
            'token_type': data.get('token_type')
        }
```

### 4.3 Add Google Drive Routes

**File:** `backend/api/integration_routes.py` (add to existing file)

```python
# ============================================================================
# GOOGLE DRIVE INTEGRATION
# ============================================================================

@integration_bp.route('/gdrive/auth', methods=['GET'])
@require_auth
def gdrive_auth():
    """Initiate Google Drive OAuth flow"""
    try:
        from connectors.gdrive_connector import GDriveConnector, GDRIVE_AVAILABLE

        if not GDRIVE_AVAILABLE:
            return jsonify({
                "success": False,
                "error": "Google API SDK not available"
            }), 500

        redirect_uri = os.getenv(
            "GDRIVE_REDIRECT_URI",
            f"{os.getenv('BACKEND_URL', 'http://localhost:5003')}/api/integrations/gdrive/callback"
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

    except Exception as e:
        print(f"[GDrive] Auth error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@integration_bp.route('/gdrive/callback', methods=['GET'])
def gdrive_callback():
    """Handle Google Drive OAuth callback"""
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

    try:
        code = request.args.get('code')
        state = request.args.get('state')
        error = request.args.get('error')

        if error:
            return redirect(f"{FRONTEND_URL}/integrations?error=gdrive_{error}")

        if not code or not state:
            return redirect(f"{FRONTEND_URL}/integrations?error=gdrive_missing_params")

        # Verify state
        state_data, error_msg = verify_oauth_state(state)
        if error_msg:
            return redirect(f"{FRONTEND_URL}/integrations?error=gdrive_invalid_state")

        if state_data.get("connector_type") != "gdrive":
            return redirect(f"{FRONTEND_URL}/integrations?error=gdrive_wrong_connector")

        from connectors.gdrive_connector import GDriveConnector
        import asyncio

        # Exchange code for tokens
        redirect_uri = state_data.get("data", {}).get("redirect_uri")
        if not redirect_uri:
            redirect_uri = os.getenv("GDRIVE_REDIRECT_URI")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        tokens = loop.run_until_complete(GDriveConnector.exchange_code(code, redirect_uri))
        loop.close()

        # Save to database
        db = get_db()
        try:
            from database.models import Connector, ConnectorType, ConnectorStatus

            connector = db.query(Connector).filter(
                Connector.tenant_id == state_data['tenant_id'],
                Connector.connector_type == ConnectorType.GDRIVE
            ).first()

            is_first = connector is None

            if connector:
                connector.access_token = tokens["access_token"]
                connector.refresh_token = tokens.get("refresh_token") or connector.refresh_token
                connector.status = ConnectorStatus.CONNECTED
                connector.is_active = True
                connector.error_message = None
            else:
                connector = Connector(
                    tenant_id=state_data['tenant_id'],
                    user_id=state_data['user_id'],
                    connector_type=ConnectorType.GDRIVE,
                    name="Google Drive",
                    status=ConnectorStatus.CONNECTED,
                    access_token=tokens["access_token"],
                    refresh_token=tokens.get("refresh_token"),
                    settings={}
                )
                db.add(connector)

            db.commit()
            connector_id = connector.id

            # Auto-sync on first connection
            if is_first:
                def run_gdrive_sync():
                    _run_connector_sync(
                        connector_id=connector_id,
                        connector_type="gdrive",
                        since=None,
                        tenant_id=state_data['tenant_id'],
                        user_id=state_data['user_id'],
                        full_sync=True
                    )

                spawn_background_task(run_gdrive_sync)

            return redirect(f"{FRONTEND_URL}/integrations?success=gdrive")

        finally:
            db.close()

    except Exception as e:
        print(f"[GDrive] Callback error: {e}")
        import traceback
        traceback.print_exc()
        return redirect(f"{FRONTEND_URL}/integrations?error=gdrive_exchange_failed")


@integration_bp.route('/gdrive/sync', methods=['POST'])
@require_auth
def gdrive_sync():
    """Trigger manual Google Drive sync"""
    db = get_db()
    try:
        from database.models import Connector, ConnectorType, ConnectorStatus

        connector = db.query(Connector).filter(
            Connector.tenant_id == g.tenant_id,
            Connector.connector_type == ConnectorType.GDRIVE
        ).first()

        if not connector:
            return jsonify({"success": False, "error": "Google Drive not connected"}), 404

        if connector.status == ConnectorStatus.SYNCING:
            return jsonify({"success": False, "error": "Sync already in progress"}), 409

        data = request.get_json() or {}
        full_sync = data.get('full_sync', False)
        since = None if full_sync else connector.last_sync_at

        sync_id = f"gdrive_{connector.id}_{datetime.now(timezone.utc).timestamp()}"

        def run_sync():
            _run_connector_sync(
                connector_id=connector.id,
                connector_type="gdrive",
                since=since,
                tenant_id=g.tenant_id,
                user_id=g.user_id,
                full_sync=full_sync,
                sync_id=sync_id
            )

        spawn_background_task(run_sync)

        return jsonify({
            "success": True,
            "message": "Sync started",
            "sync_id": sync_id
        })

    finally:
        db.close()


@integration_bp.route('/gdrive/disconnect', methods=['POST'])
@require_auth
def gdrive_disconnect():
    """Disconnect Google Drive integration"""
    db = get_db()
    try:
        from database.models import Connector, ConnectorType, ConnectorStatus

        connector = db.query(Connector).filter(
            Connector.tenant_id == g.tenant_id,
            Connector.connector_type == ConnectorType.GDRIVE
        ).first()

        if not connector:
            return jsonify({"success": False, "error": "Google Drive not connected"}), 404

        connector.access_token = None
        connector.refresh_token = None
        connector.status = ConnectorStatus.DISCONNECTED
        connector.is_active = False
        db.commit()

        return jsonify({"success": True, "message": "Google Drive disconnected"})

    finally:
        db.close()


@integration_bp.route('/gdrive/folders', methods=['GET'])
@require_auth
def gdrive_folders():
    """Get list of Google Drive folders for selection"""
    db = get_db()
    try:
        from database.models import Connector, ConnectorType

        connector = db.query(Connector).filter(
            Connector.tenant_id == g.tenant_id,
            Connector.connector_type == ConnectorType.GDRIVE
        ).first()

        if not connector or not connector.access_token:
            return jsonify({"success": False, "error": "Google Drive not connected"}), 404

        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        credentials = Credentials(
            token=connector.access_token,
            refresh_token=connector.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET")
        )

        service = build('drive', 'v3', credentials=credentials)

        # Get folders
        response = service.files().list(
            q="mimeType='application/vnd.google-apps.folder' and trashed=false",
            fields="files(id, name, parents)",
            pageSize=100
        ).execute()

        folders = response.get('files', [])

        return jsonify({
            "success": True,
            "folders": [
                {
                    "id": f['id'],
                    "name": f['name'],
                    "parent": f.get('parents', [None])[0]
                }
                for f in folders
            ]
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

    finally:
        db.close()
```

---

## Phase 5: Update Integration List Endpoint

**File:** `backend/api/integration_routes.py`

In the `list_integrations()` function, add the three new integrations:

```python
@integration_bp.route('', methods=['GET'])
@require_auth
def list_integrations():
    """List all available integrations and their status"""
    db = get_db()
    try:
        from database.models import Connector, ConnectorType

        # Get all connectors for this tenant
        connectors = db.query(Connector).filter(
            Connector.tenant_id == g.tenant_id
        ).all()

        connector_map = {c.connector_type: c for c in connectors}

        integrations = []

        # ... existing integrations (Gmail, Slack, Box, GitHub, etc.) ...

        # ===== ADD THESE THREE =====

        # Notion
        notion = connector_map.get(ConnectorType.NOTION)
        integrations.append({
            "type": "notion",
            "name": "Notion",
            "description": "Sync pages and databases from your Notion workspace",
            "icon": "notion",
            "auth_type": "oauth",
            "status": notion.status.value if notion else "not_configured",
            "connector_id": notion.id if notion else None,
            "last_sync_at": notion.last_sync_at.isoformat() if notion and notion.last_sync_at else None,
            "total_items_synced": notion.total_items_synced if notion else 0,
            "error_message": notion.error_message if notion else None
        })

        # Zotero
        zotero = connector_map.get(ConnectorType.ZOTERO)
        integrations.append({
            "type": "zotero",
            "name": "Zotero",
            "description": "Sync research papers, citations, and annotations",
            "icon": "zotero",
            "auth_type": "api_key",
            "status": zotero.status.value if zotero else "not_configured",
            "connector_id": zotero.id if zotero else None,
            "last_sync_at": zotero.last_sync_at.isoformat() if zotero and zotero.last_sync_at else None,
            "total_items_synced": zotero.total_items_synced if zotero else 0,
            "error_message": zotero.error_message if zotero else None,
            "settings": zotero.settings if zotero else None
        })

        # Google Drive
        gdrive = connector_map.get(ConnectorType.GDRIVE)
        integrations.append({
            "type": "gdrive",
            "name": "Google Drive",
            "description": "Sync documents and files from Google Drive",
            "icon": "gdrive",
            "auth_type": "oauth",
            "status": gdrive.status.value if gdrive else "not_configured",
            "connector_id": gdrive.id if gdrive else None,
            "last_sync_at": gdrive.last_sync_at.isoformat() if gdrive and gdrive.last_sync_at else None,
            "total_items_synced": gdrive.total_items_synced if gdrive else 0,
            "error_message": gdrive.error_message if gdrive else None
        })

        return jsonify({
            "success": True,
            "integrations": integrations
        })

    finally:
        db.close()
```

---

## Phase 6: Update Connector Sync Function

**File:** `backend/api/integration_routes.py`

Update `_run_connector_sync()` to handle the new connector types:

```python
def _run_connector_sync(connector_id, connector_type, since, tenant_id, user_id, full_sync=False, sync_id=None):
    """Run connector sync in background thread"""

    # ... existing code ...

    # Add these imports at the top of the function:
    if connector_type == "notion":
        from connectors.notion_connector import NotionConnector
        connector_class = NotionConnector
    elif connector_type == "zotero":
        from connectors.zotero_connector import ZoteroConnector
        connector_class = ZoteroConnector
    elif connector_type == "gdrive":
        from connectors.gdrive_connector import GDriveConnector
        connector_class = GDriveConnector
    # ... existing elif branches ...

    # Build connector config
    if connector_type == "zotero":
        # Zotero needs user_id from settings
        credentials = {
            "api_key": db_connector.access_token,
            "user_id": db_connector.settings.get("user_id")
        }
    else:
        credentials = {
            "access_token": db_connector.access_token,
            "refresh_token": db_connector.refresh_token
        }

    # ... rest of sync logic ...
```

---

## Phase 7: Frontend Updates

### 7.1 Add Integration Cards

**File:** `frontend/components/integrations/Integrations.tsx`

Add card configurations for the three new integrations:

```typescript
// Add to integration card definitions

const INTEGRATION_CONFIGS = {
  // ... existing configs ...

  notion: {
    name: "Notion",
    description: "Sync pages and databases from your Notion workspace",
    icon: (
      <svg viewBox="0 0 24 24" width="32" height="32" fill="currentColor">
        <path d="M4.459 4.208c.746.606 1.026.56 2.428.466l13.215-.793c.28 0 .047-.28-.046-.326L17.86 1.968c-.42-.326-.981-.7-2.055-.607L3.01 2.295c-.466.046-.56.28-.374.466l1.823 1.447zm2.896 2.335v13.746c0 .653.28 1.073 1.027 1.027l14.242-.84c.746-.046 1.073-.466 1.073-1.027V5.562c0-.56-.327-.793-.887-.746l-14.383.84c-.56.046-1.072.28-1.072.887zM17.858 7.227c.093.42 0 .84-.42.887l-.7.093v10.07c-.607.326-1.166.513-1.632.513-.746 0-.933-.234-1.493-.887l-4.57-7.185v6.951l1.446.327s0 .84-1.166.84l-3.218.186c-.093-.186 0-.653.327-.746l.84-.233v-9.189L6.09 8.067c-.093-.42.14-1.026.793-1.073l3.454-.233 4.756 7.278v-6.438l-1.213-.14c-.093-.513.28-.886.746-.933l3.218-.28z"/>
      </svg>
    ),
    authType: "oauth",
    color: "#000000"
  },

  zotero: {
    name: "Zotero",
    description: "Sync research papers, citations, and annotations",
    icon: (
      <svg viewBox="0 0 24 24" width="32" height="32" fill="currentColor">
        <path d="M21.231 2.462H7.18v2.923l7.103 8.308H7.487v3.538h6.622v2.923H3.646v-2.923l7.103-8.308h-6.41V5.385h14.052v2.923l-7.103 8.308h7.943v-2.923L21.231 2.462z"/>
      </svg>
    ),
    authType: "api_key",
    color: "#CC2936"
  },

  gdrive: {
    name: "Google Drive",
    description: "Sync documents and files from Google Drive",
    icon: (
      <svg viewBox="0 0 24 24" width="32" height="32">
        <path fill="#4285F4" d="M12 0L4 8l4 6.93L16 8z"/>
        <path fill="#0F9D58" d="M4 8l-4 7h8l4-7z"/>
        <path fill="#FFCD40" d="M12 0l8 8-4 6.93L8 8z"/>
        <path fill="#4285F4" d="M20 15h-8l-4 7h8z"/>
        <path fill="#0F9D58" d="M0 15l4 7h8l-4-7z"/>
        <path fill="#FFCD40" d="M16 15l4-7 4 7h-8z"/>
      </svg>
    ),
    authType: "oauth",
    color: "#4285F4"
  }
};
```

### 7.2 Add Zotero Configuration Modal

**File:** `frontend/components/integrations/ZoteroConfigModal.tsx` (new file)

```typescript
'use client';

import { useState } from 'react';
import axios from 'axios';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export default function ZoteroConfigModal({ isOpen, onClose, onSuccess }: Props) {
  const [apiKey, setApiKey] = useState('');
  const [userId, setUserId] = useState('');
  const [libraryType, setLibraryType] = useState<'user' | 'group'>('user');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleConnect = async () => {
    if (!apiKey.trim() || !userId.trim()) {
      setError('API Key and User ID are required');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const token = localStorage.getItem('accessToken');
      const response = await axios.post(
        `${process.env.NEXT_PUBLIC_API_URL}/api/integrations/zotero/configure`,
        {
          api_key: apiKey.trim(),
          user_id: userId.trim(),
          library_type: libraryType
        },
        {
          headers: { Authorization: `Bearer ${token}` }
        }
      );

      if (response.data.success) {
        onSuccess();
        onClose();
      } else {
        setError(response.data.error || 'Configuration failed');
      }
    } catch (err: any) {
      setError(err.response?.data?.error || 'Connection failed');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
        <h2 className="text-xl font-semibold mb-4">Connect Zotero</h2>

        <p className="text-sm text-gray-600 mb-4">
          To connect Zotero, you'll need your API key and User ID.
          <a
            href="https://www.zotero.org/settings/keys"
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:underline ml-1"
          >
            Get your API key here
          </a>
        </p>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              API Key
            </label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Enter your Zotero API key"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              User ID (numeric)
            </label>
            <input
              type="text"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              placeholder="e.g., 1234567"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500"
            />
            <p className="text-xs text-gray-500 mt-1">
              Find this at zotero.org/settings/keys
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Library Type
            </label>
            <select
              value={libraryType}
              onChange={(e) => setLibraryType(e.target.value as 'user' | 'group')}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500"
            >
              <option value="user">Personal Library</option>
              <option value="group">Group Library</option>
            </select>
          </div>

          {error && (
            <div className="text-red-600 text-sm">{error}</div>
          )}
        </div>

        <div className="flex gap-3 mt-6">
          <button
            onClick={onClose}
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={handleConnect}
            disabled={loading}
            className="flex-1 px-4 py-2 bg-black text-white rounded-lg hover:bg-gray-800 disabled:opacity-50"
          >
            {loading ? 'Connecting...' : 'Connect'}
          </button>
        </div>
      </div>
    </div>
  );
}
```

### 7.3 Update Documents Display

**File:** `frontend/components/documents/Documents.tsx`

Add source type badges and icons for new integrations:

```typescript
// In the source badge/icon rendering:

const getSourceIcon = (source: string) => {
  switch (source) {
    // ... existing cases ...
    case 'notion':
      return <NotionIcon />;
    case 'zotero':
      return <ZoteroIcon />;
    case 'gdrive':
      return <GDriveIcon />;
    default:
      return <DocumentIcon />;
  }
};

const getSourceLabel = (source: string) => {
  switch (source) {
    // ... existing cases ...
    case 'notion':
      return 'Notion';
    case 'zotero':
      return 'Zotero';
    case 'gdrive':
      return 'Google Drive';
    default:
      return source;
  }
};
```

---

## Phase 8: Testing Plan

### 8.1 Unit Tests

```python
# backend/tests/test_notion_connector.py
# backend/tests/test_zotero_connector.py
# backend/tests/test_gdrive_connector.py

def test_notion_connect():
    """Test Notion connection with valid token"""
    pass

def test_notion_sync():
    """Test Notion page sync"""
    pass

def test_zotero_connect():
    """Test Zotero connection with API key"""
    pass

def test_gdrive_oauth_flow():
    """Test Google Drive OAuth token exchange"""
    pass
```

### 8.2 Integration Tests

1. **Notion OAuth Flow**
   - Click "Connect Notion" → redirects to Notion auth
   - Authorize → redirects back with success
   - Sync runs → documents appear in Documents page

2. **Zotero API Key Flow**
   - Click "Connect Zotero" → modal opens
   - Enter API key + User ID → validates and saves
   - Sync runs → research papers appear

3. **Google Drive OAuth Flow**
   - Click "Connect Google Drive" → redirects to Google auth
   - Authorize → redirects back with success
   - Sync runs → files appear in Documents page

### 8.3 Manual Testing Checklist

- [ ] Notion: OAuth flow completes successfully
- [ ] Notion: Pages sync with correct content
- [ ] Notion: Database entries sync with properties
- [ ] Notion: Incremental sync only fetches new/modified pages
- [ ] Zotero: API key validation works
- [ ] Zotero: Papers sync with abstract and metadata
- [ ] Zotero: Notes and annotations included
- [ ] Zotero: Collections filtering works
- [ ] Google Drive: OAuth flow completes successfully
- [ ] Google Drive: Documents sync with content extraction
- [ ] Google Drive: Google Docs export as text works
- [ ] Google Drive: Folder filtering works
- [ ] All: Documents appear in Documents page with correct source badges
- [ ] All: Classification runs on synced documents
- [ ] All: Embedding works for synced documents
- [ ] All: Search returns results from new sources

---

## Phase 9: Environment Variables Summary

### Development (.env)

```bash
# Notion
NOTION_CLIENT_ID=your_notion_client_id
NOTION_CLIENT_SECRET=your_notion_client_secret
NOTION_REDIRECT_URI=http://localhost:5003/api/integrations/notion/callback

# Zotero (API key - no OAuth secrets needed)
# Users provide their own API keys

# Google Drive (reuses existing Google OAuth app)
GDRIVE_REDIRECT_URI=http://localhost:5003/api/integrations/gdrive/callback
# Note: Add Drive scopes to your Google OAuth app in Google Cloud Console
```

### Production (Render)

```bash
# Notion
NOTION_CLIENT_ID=your_notion_client_id
NOTION_CLIENT_SECRET=your_notion_client_secret
NOTION_REDIRECT_URI=https://your-backend.onrender.com/api/integrations/notion/callback

# Google Drive
GDRIVE_REDIRECT_URI=https://your-backend.onrender.com/api/integrations/gdrive/callback
```

---

## Phase 10: Rollout Plan

### Step 1: Backend Development (Do First)
1. Create connector files (notion_connector.py, zotero_connector.py, gdrive_connector.py)
2. Update database/models.py with new ConnectorType values
3. Add routes to integration_routes.py
4. Test each connector independently

### Step 2: Frontend Updates
1. Add integration card configs
2. Create ZoteroConfigModal component
3. Update Documents.tsx source display
4. Test OAuth flows in browser

### Step 3: Testing
1. Run unit tests
2. Run integration tests
3. Manual testing with real accounts

### Step 4: Deploy
1. Set environment variables on Render
2. Deploy backend
3. Deploy frontend
4. Verify OAuth redirects work in production

---

## Files Summary

### New Files to Create (6)

| File | Purpose | Lines (est.) |
|------|---------|--------------|
| `backend/connectors/notion_connector.py` | Notion connector | ~400 |
| `backend/connectors/zotero_connector.py` | Zotero connector | ~300 |
| `backend/connectors/gdrive_connector.py` | Google Drive connector | ~350 |
| `frontend/components/integrations/ZoteroConfigModal.tsx` | Zotero config UI | ~120 |
| `backend/tests/test_notion_connector.py` | Notion tests | ~100 |
| `backend/tests/test_zotero_connector.py` | Zotero tests | ~100 |

### Files to Modify (5)

| File | Changes |
|------|---------|
| `backend/database/models.py` | Add NOTION, ZOTERO, GDRIVE to ConnectorType enum |
| `backend/api/integration_routes.py` | Add OAuth routes + sync functions for 3 integrations |
| `frontend/components/integrations/Integrations.tsx` | Add integration card configs + Zotero modal |
| `frontend/components/documents/Documents.tsx` | Add source icons/labels for new integrations |
| `.env` / `.env.production` | Add new environment variables |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Notion API rate limits | Implement exponential backoff, respect 429 responses |
| Zotero OAuth 1.0a complexity | Use API key auth instead (simpler, well-documented) |
| Google Drive token refresh | Use refresh_token, handle 401 with auto-refresh |
| Large file downloads | Set max_file_size_mb limit, skip oversized files |
| PDF extraction failures | Graceful fallback to "[PDF document: filename]" |
| Sync timeouts | Run in background thread, implement progress tracking |

---

## Success Criteria

1. All three integrations appear on Integrations page
2. OAuth/API key flows complete without errors
3. Documents sync and appear in Documents page with correct metadata
4. Documents are classified and embedded automatically
5. Search returns results from all new sources
6. No breaking changes to existing integrations
