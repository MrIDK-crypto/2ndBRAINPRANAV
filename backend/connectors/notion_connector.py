"""
Notion Connector for 2nd Brain
Syncs pages and databases from Notion workspaces
"""

import os
import base64
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
import requests

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
    print("[Notion] notion-client not installed. Run: pip install notion-client")


class NotionConnector(BaseConnector):
    """Connector for Notion workspaces - synchronous implementation"""

    CONNECTOR_TYPE = "notion"
    REQUIRED_CREDENTIALS = ["access_token"]
    OPTIONAL_SETTINGS = {
        "database_ids": [],           # Specific databases to sync (empty = all)
        "include_archived": False,    # Include archived pages
        "max_blocks_per_page": 200,   # Limit blocks fetched per page
        "max_pages": 500              # Maximum pages to sync
    }

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.client: Optional[Client] = None
        self.workspace_name: str = ""
        self.workspace_id: str = ""

    def connect(self) -> bool:
        """Establish connection to Notion API"""
        if not NOTION_AVAILABLE:
            self._set_error("Notion SDK not installed")
            return False

        try:
            self.status = ConnectorStatus.CONNECTING
            access_token = self.config.credentials.get("access_token")

            if not access_token:
                self._set_error("Missing access_token")
                return False

            self.client = Client(auth=access_token)

            # Test connection and get workspace info
            me = self.client.users.me()
            self.workspace_name = me.get("name", "Notion Workspace")

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

    def disconnect(self) -> bool:
        """Disconnect from Notion"""
        self.client = None
        self.status = ConnectorStatus.DISCONNECTED
        return True

    def test_connection(self) -> bool:
        """Verify connection is still valid"""
        if not self.client:
            return False
        try:
            self.client.users.me()
            return True
        except Exception:
            return False

    def sync(self, since: Optional[datetime] = None) -> List[Document]:
        """Sync pages from Notion"""
        if not self.client:
            if not self.connect():
                return []

        self.status = ConnectorStatus.SYNCING
        documents = []

        try:
            max_pages = self.config.settings.get("max_pages", 500)
            print(f"[Notion] Starting sync (max_pages={max_pages})")

            has_more = True
            start_cursor = None
            page_count = 0

            while has_more and page_count < max_pages:
                search_params = {
                    "filter": {"property": "object", "value": "page"},
                    "sort": {"direction": "descending", "timestamp": "last_edited_time"},
                    "page_size": 100
                }

                if start_cursor:
                    search_params["start_cursor"] = start_cursor

                results = self.client.search(**search_params)
                pages = results.get("results", [])
                print(f"[Notion] Found {len(pages)} pages in batch")

                for page in pages:
                    # Filter by modified time if incremental
                    if since:
                        last_edited = page.get("last_edited_time", "")
                        if last_edited:
                            try:
                                edited_dt = datetime.fromisoformat(last_edited.replace("Z", "+00:00"))
                                if edited_dt < since:
                                    continue
                            except:
                                pass

                    # Skip archived unless configured
                    if page.get("archived") and not self.config.settings.get("include_archived"):
                        continue

                    doc = self._page_to_document(page)
                    if doc:
                        documents.append(doc)
                        page_count += 1
                        print(f"[Notion] Processed page {page_count}: {doc.title[:50] if doc.title else 'Untitled'}")

                        if page_count >= max_pages:
                            break

                has_more = results.get("has_more", False)
                start_cursor = results.get("next_cursor")

            self.config.last_sync = datetime.now(timezone.utc)
            self.status = ConnectorStatus.CONNECTED
            print(f"[Notion] Sync complete: {len(documents)} documents")

        except Exception as e:
            self._set_error(f"Sync failed: {str(e)}")
            import traceback
            traceback.print_exc()

        return documents

    def get_document(self, doc_id: str) -> Optional[Document]:
        """Retrieve a specific page by ID"""
        if not self.client:
            self.connect()

        try:
            page_id = doc_id.replace("notion_", "")
            page = self.client.pages.retrieve(page_id)
            return self._page_to_document(page)
        except Exception as e:
            self._set_error(f"Failed to get document: {str(e)}")
            return None

    def _page_to_document(self, page: Dict[str, Any]) -> Optional[Document]:
        """Convert Notion page to Document object"""
        try:
            page_id = page["id"]
            properties = page.get("properties", {})

            title = self._extract_title(properties)
            content = self._get_page_content(page_id)

            if not content.strip() and not title:
                return None

            # Build metadata
            metadata = {
                "page_id": page_id,
                "url": page.get("url", ""),
                "archived": page.get("archived", False),
                "workspace": self.workspace_name
            }

            # Parse timestamp
            created_time = page.get("created_time", "")
            timestamp = None
            if created_time:
                try:
                    timestamp = datetime.fromisoformat(created_time.replace("Z", "+00:00"))
                except:
                    pass

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
        for prop_name in ["title", "Title", "Name", "name"]:
            if prop_name in properties:
                prop = properties[prop_name]
                if prop.get("type") == "title":
                    title_array = prop.get("title", [])
                    return "".join([t.get("plain_text", "") for t in title_array])

        for prop in properties.values():
            if prop.get("type") == "title":
                title_array = prop.get("title", [])
                return "".join([t.get("plain_text", "") for t in title_array])

        return ""

    def _get_page_content(self, page_id: str, depth: int = 0) -> str:
        """Fetch and concatenate all blocks from a page"""
        content_parts = []
        max_blocks = self.config.settings.get("max_blocks_per_page", 200)

        if depth > 3:
            return ""

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

                    if block.get("has_children") and block_count < max_blocks:
                        child_content = self._get_page_content(block["id"], depth + 1)
                        if child_content:
                            content_parts.append(child_content)

                has_more = response.get("has_more", False)
                start_cursor = response.get("next_cursor")

        except Exception as e:
            print(f"[Notion] Error fetching blocks for {page_id}: {e}")

        return "\n".join(content_parts)

    def _extract_block_text(self, block: Dict) -> str:
        """Extract text from a Notion block"""
        block_type = block.get("type", "")
        block_data = block.get(block_type, {})

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
        elif block_type == "code":
            language = block_data.get("language", "text")
            code = get_rich_text(block_data)
            return f"```{language}\n{code}\n```"
        elif block_type == "quote":
            return f"> {get_rich_text(block_data)}"
        elif block_type == "divider":
            return "---"

        return ""

    @classmethod
    def get_auth_url(cls, redirect_uri: str, state: str) -> str:
        """Generate Notion OAuth authorization URL"""
        client_id = os.getenv("NOTION_CLIENT_ID", "")
        return (
            f"https://api.notion.com/v1/oauth/authorize"
            f"?client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&response_type=code"
            f"&owner=user"
            f"&state={state}"
        )

    @classmethod
    def exchange_code(cls, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        client_id = os.getenv("NOTION_CLIENT_ID", "")
        client_secret = os.getenv("NOTION_CLIENT_SECRET", "")

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
