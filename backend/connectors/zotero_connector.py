"""
Zotero Connector
Connects to Zotero API using OAuth 1.0a to sync research papers and PDFs.
"""

import os
import io
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any

from .base_connector import BaseConnector, ConnectorConfig, ConnectorStatus, Document

# OAuth 1.0a support
try:
    from requests_oauthlib import OAuth1Session
    OAUTH_AVAILABLE = True
except ImportError:
    OAUTH_AVAILABLE = False

# Zotero API client
try:
    from pyzotero import zotero
    PYZOTERO_AVAILABLE = True
except ImportError:
    PYZOTERO_AVAILABLE = False

# PDF text extraction
try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False


class ZoteroConnector(BaseConnector):
    """
    Zotero connector for extracting research papers and library items.

    Features:
    - OAuth 1.0a authentication
    - Sync library items (papers, books, etc.)
    - Download and extract text from PDF attachments
    - Incremental sync using library version numbers
    """

    CONNECTOR_TYPE = "zotero"
    REQUIRED_CREDENTIALS = ["api_key", "user_id"]
    OPTIONAL_SETTINGS = {
        "sync_pdfs": True,  # Download and process PDFs
        "max_items": None,  # No limit - sync all items
        "collections": [],  # Specific collections to sync (empty = all)
    }

    # Zotero OAuth 1.0a endpoints
    REQUEST_TOKEN_URL = "https://www.zotero.org/oauth/request"
    AUTHORIZE_URL = "https://www.zotero.org/oauth/authorize"
    ACCESS_TOKEN_URL = "https://www.zotero.org/oauth/access"

    # OAuth credentials from environment
    @classmethod
    def _get_client_credentials(cls) -> tuple:
        """Get OAuth client credentials from environment"""
        client_key = os.getenv("ZOTERO_CLIENT_KEY", "")
        client_secret = os.getenv("ZOTERO_CLIENT_SECRET", "")
        return client_key, client_secret

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.zot = None  # pyzotero client

    async def connect(self) -> bool:
        """Connect to Zotero API"""
        if not PYZOTERO_AVAILABLE:
            self._set_error("pyzotero not installed. Run: pip install pyzotero")
            return False

        try:
            self.status = ConnectorStatus.CONNECTING

            api_key = self.config.credentials.get("api_key")
            user_id = self.config.credentials.get("user_id")

            if not api_key or not user_id:
                self._set_error("Missing Zotero API key or user ID")
                return False

            # Create Zotero client
            self.zot = zotero.Zotero(user_id, 'user', api_key)

            # Test connection by fetching library version
            try:
                # This will raise an exception if credentials are invalid
                self.zot.num_items()
                self.status = ConnectorStatus.CONNECTED
                self._clear_error()
                return True
            except Exception as e:
                self._set_error(f"Invalid Zotero credentials: {str(e)}")
                return False

        except Exception as e:
            self._set_error(f"Failed to connect: {str(e)}")
            return False

    async def disconnect(self) -> bool:
        """Disconnect from Zotero API"""
        self.zot = None
        self.status = ConnectorStatus.DISCONNECTED
        return True

    async def test_connection(self) -> bool:
        """Test Zotero connection"""
        if not self.zot:
            return False

        try:
            self.zot.num_items()
            return True
        except Exception:
            return False

    @classmethod
    def get_oauth_session(cls, callback_url: str) -> tuple:
        """
        Start OAuth 1.0a flow - get request token.

        Returns:
            tuple: (OAuth1Session, request_token, authorize_url) or (None, None, error_message)
        """
        if not OAUTH_AVAILABLE:
            return None, None, "requests-oauthlib not installed"

        client_key, client_secret = cls._get_client_credentials()

        if not client_key or not client_secret:
            return None, None, "Zotero OAuth credentials not configured"

        try:
            # Step 1: Get request token
            oauth = OAuth1Session(
                client_key,
                client_secret=client_secret,
                callback_uri=callback_url
            )

            fetch_response = oauth.fetch_request_token(cls.REQUEST_TOKEN_URL)
            resource_owner_key = fetch_response.get('oauth_token')
            resource_owner_secret = fetch_response.get('oauth_token_secret')

            # Step 2: Build authorization URL
            authorization_url = oauth.authorization_url(cls.AUTHORIZE_URL)

            # Return session data needed for callback
            return {
                'oauth_token': resource_owner_key,
                'oauth_token_secret': resource_owner_secret
            }, authorization_url, None

        except Exception as e:
            return None, None, str(e)

    @classmethod
    def exchange_verifier_for_token(
        cls,
        oauth_token: str,
        oauth_token_secret: str,
        oauth_verifier: str
    ) -> tuple:
        """
        Exchange OAuth verifier for access token.

        Returns:
            tuple: (credentials_dict, error_message)
            credentials_dict contains: api_key, user_id
        """
        if not OAUTH_AVAILABLE:
            return None, "requests-oauthlib not installed"

        client_key, client_secret = cls._get_client_credentials()

        try:
            oauth = OAuth1Session(
                client_key,
                client_secret=client_secret,
                resource_owner_key=oauth_token,
                resource_owner_secret=oauth_token_secret,
                verifier=oauth_verifier
            )

            oauth_tokens = oauth.fetch_access_token(cls.ACCESS_TOKEN_URL)

            # Zotero returns the API key and userID in the access token response
            api_key = oauth_tokens.get('oauth_token')
            user_id = oauth_tokens.get('userID')
            username = oauth_tokens.get('username', 'Zotero User')

            if not api_key or not user_id:
                return None, "Failed to get Zotero API key or user ID"

            return {
                'api_key': api_key,
                'user_id': user_id,
                'username': username
            }, None

        except Exception as e:
            return None, str(e)

    async def sync(self, since: Optional[datetime] = None) -> List[Document]:
        """Sync items from Zotero library"""
        if not self.zot:
            await self.connect()

        if self.status != ConnectorStatus.CONNECTED:
            return []

        self.status = ConnectorStatus.SYNCING
        documents = []

        try:
            # Get library version for incremental sync
            stored_version = self.config.settings.get("library_version")

            # Build query parameters
            params = {}
            if stored_version and not since:
                # Incremental sync
                params['since'] = stored_version

            # Get all items
            print(f"[Zotero] Fetching items with params: {params}", flush=True)
            items = self.zot.everything(self.zot.items(**params))
            print(f"[Zotero] Found {len(items)} items", flush=True)

            # Process each item
            for item in items:
                doc = await self._item_to_document(item)
                if doc:
                    documents.append(doc)

            # Update library version for next sync
            try:
                # Get current library version from the last API response
                # pyzotero stores the last-modified-version in the Zotero object
                new_version = getattr(self.zot, 'last_modified_version', None)
                if not new_version:
                    # Fallback: make a lightweight API call and check response headers
                    self.zot.items(limit=1)
                    # pyzotero >= 1.5 stores headers on the response
                    if hasattr(self.zot, 'last_modified_version'):
                        new_version = self.zot.last_modified_version
                if new_version:
                    self.config.settings['library_version'] = str(new_version)
                    print(f"[Zotero] Updated library version to {new_version}", flush=True)
            except Exception as e:
                print(f"[Zotero] Could not get library version: {e}", flush=True)

            # Update stats
            self.sync_stats = {
                "documents_synced": len(documents),
                "sync_time": datetime.now(timezone.utc).isoformat()
            }

            self.config.last_sync = datetime.now(timezone.utc)
            self.status = ConnectorStatus.CONNECTED

        except Exception as e:
            self._set_error(f"Sync failed: {str(e)}")
            import traceback
            traceback.print_exc()

        return documents

    async def get_document(self, doc_id: str) -> Optional[Document]:
        """Get a specific item by key"""
        if not self.zot:
            await self.connect()

        try:
            # Extract Zotero item key from doc_id
            item_key = doc_id.replace("zotero_", "")
            item = self.zot.item(item_key)
            return await self._item_to_document(item)
        except Exception as e:
            self._set_error(f"Failed to get document: {str(e)}")
            return None

    async def _item_to_document(self, item: Dict) -> Optional[Document]:
        """Convert Zotero item to Document"""
        try:
            data = item.get('data', {})
            item_type = data.get('itemType', '')
            item_key = data.get('key', '')

            print(f"[Zotero] Processing item: key={item_key}, type={item_type}", flush=True)
            print(f"[Zotero] Item data keys: {list(data.keys())}", flush=True)

            # Skip notes (but NOT attachments - we want to process standalone PDFs)
            if item_type == 'note':
                print(f"[Zotero] Skipping note item: {item_key}", flush=True)
                return None

            # Handle standalone attachments (PDFs without parent items)
            if item_type == 'attachment':
                # Check if this is a standalone attachment (no parentItem)
                parent_item = data.get('parentItem')
                if parent_item:
                    # Child attachment - will be processed via parent
                    print(f"[Zotero] Skipping child attachment {item_key} (parent: {parent_item})", flush=True)
                    return None

                # Standalone attachment - process it
                print(f"[Zotero] Processing standalone attachment: {item_key}", flush=True)
                print(f"[Zotero] Attachment data: {data}", flush=True)
                content_type = data.get('contentType', '')
                filename = data.get('filename', '')

                # Try multiple fields for attachment title
                title = data.get('title') or filename or data.get('note', '')[:100] if data.get('note') else None

                # If still no title, extract from URL or use fallback
                if not title:
                    link_url = data.get('url', '')
                    if link_url:
                        from urllib.parse import urlparse, unquote
                        parsed = urlparse(link_url)
                        path = unquote(parsed.path)
                        segments = [s for s in path.split('/') if s]
                        if segments:
                            title = segments[-1].replace('.pdf', '').replace('-', ' ').replace('_', ' ').title()

                if not title:
                    title = f"Attachment - {item_key}"

                print(f"[Zotero] Attachment title: '{title}'", flush=True)

                # Try to extract content from PDF
                pdf_content = ""
                if content_type == 'application/pdf':
                    try:
                        pdf_bytes = self.zot.file(item_key)
                        pdf_content = self._extract_pdf_text(pdf_bytes, filename or "document.pdf")
                        print(f"[Zotero] Extracted {len(pdf_content)} chars from standalone PDF", flush=True)
                    except Exception as pdf_err:
                        print(f"[Zotero] Failed to extract standalone PDF: {pdf_err}", flush=True)

                content = f"Title: {title}\nFilename: {filename}\n"
                if pdf_content:
                    content += f"\n--- Full Text ---\n{pdf_content}"

                return Document(
                    doc_id=f"zotero_{item_key}",
                    source="zotero",
                    content=content,
                    title=title,
                    metadata={
                        "item_key": item_key,
                        "item_type": "attachment",
                        "filename": filename,
                        "content_type": content_type,
                        "has_pdf": bool(pdf_content),
                        "authors": [],
                        "tags": [t.get('tag', '') for t in data.get('tags', [])]
                    },
                    timestamp=None,
                    author="Unknown",
                    url=data.get('url') or self._build_zotero_url(item_key),
                    doc_type="document"
                )

            # Regular items (journalArticle, book, etc.)
            # Extract metadata - try MANY fields for title (different item types use different fields)
            print(f"[Zotero] Full item data: {data}", flush=True)

            title = (
                data.get('title') or
                data.get('name') or
                data.get('shortTitle') or
                data.get('websiteTitle') or  # For webpage items
                data.get('blogTitle') or     # For blog posts
                data.get('forumTitle') or    # For forum posts
                data.get('dictionaryTitle') or
                data.get('encyclopediaTitle') or
                data.get('proceedingsTitle') or
                data.get('programTitle') or
                data.get('filename') or
                data.get('caseName') or      # For legal cases
                data.get('subject') or       # For email/letter
                data.get('nameOfAct') or     # For statutes
                None
            )

            # If still no title, try to extract from URL
            if not title:
                item_url = data.get('url', '')
                if item_url:
                    # Extract meaningful part from URL
                    from urllib.parse import urlparse, unquote
                    parsed = urlparse(item_url)
                    path = unquote(parsed.path)
                    # Get last meaningful segment
                    segments = [s for s in path.split('/') if s and s not in ['index.html', 'index.php']]
                    if segments:
                        title = segments[-1].replace('-', ' ').replace('_', ' ').replace('.html', '').replace('.php', '').replace('.pdf', '')
                        title = title.title()  # Capitalize words
                        print(f"[Zotero] Extracted title from URL: '{title}'", flush=True)

            # Last resort: use item type + key
            if not title:
                title = f"{item_type.replace('_', ' ').title()} - {item_key}"
                print(f"[Zotero] Using fallback title: '{title}'", flush=True)

            print(f"[Zotero] Final title: '{title}'", flush=True)

            creators = data.get('creators', [])
            abstract = data.get('abstractNote', '')
            date = data.get('date', '')
            doi = data.get('DOI', '')
            url = data.get('url', '')
            publication = data.get('publicationTitle', '') or data.get('bookTitle', '') or data.get('journalAbbreviation', '')
            tags = [t.get('tag', '') for t in data.get('tags', [])]

            # Build author string - include all creator types
            authors = []
            for creator in creators:
                creator_type = creator.get('creatorType', 'author')
                first_name = creator.get('firstName', '')
                last_name = creator.get('lastName', '')
                name = creator.get('name', '')  # Some creators use 'name' instead of first/last

                if name:
                    authors.append(name)
                elif first_name or last_name:
                    full_name = f"{first_name} {last_name}".strip()
                    if full_name:
                        authors.append(full_name)

            author_str = ', '.join(authors) if authors else 'Unknown'
            print(f"[Zotero] Authors: {author_str}", flush=True)

            # Build content string
            content_parts = [f"Title: {title}"]
            if authors:
                content_parts.append(f"Authors: {author_str}")
            if publication:
                content_parts.append(f"Publication: {publication}")
            if date:
                content_parts.append(f"Date: {date}")
            if doi:
                content_parts.append(f"DOI: {doi}")
            if abstract:
                content_parts.append(f"\nAbstract:\n{abstract}")

            # Try to get PDF content if enabled - NO LIMITS
            pdf_content = ""
            if self.config.settings.get("sync_pdfs", True):
                pdf_content = await self._get_pdf_content(item_key)
                if pdf_content:
                    content_parts.append(f"\n\n--- Full Text ---\n{pdf_content}")
                    print(f"[Zotero] Added {len(pdf_content)} chars of PDF content", flush=True)

            content = '\n'.join(content_parts)

            # Parse date
            timestamp = None
            if date:
                try:
                    # Try various date formats
                    for fmt in ['%Y-%m-%d', '%Y-%m', '%Y', '%B %d, %Y', '%d %B %Y', '%Y/%m/%d']:
                        try:
                            timestamp = datetime.strptime(date, fmt)
                            break
                        except ValueError:
                            continue
                except Exception:
                    pass

            doc = Document(
                doc_id=f"zotero_{item_key}",
                source="zotero",
                content=content,
                title=title,
                metadata={
                    "item_key": item_key,
                    "item_type": item_type,
                    "authors": authors,
                    "publication": publication,
                    "doi": doi,
                    "url": url,
                    "tags": tags,
                    "has_pdf": bool(pdf_content),
                    "abstract": abstract[:500] if abstract else ""
                },
                timestamp=timestamp,
                author=author_str,
                url=url or self._build_zotero_url(item_key),
                doc_type="research_paper"
            )

            print(f"[Zotero] Created document: id={doc.doc_id}, title='{doc.title}', url='{doc.url}'", flush=True)
            return doc

        except Exception as e:
            print(f"[Zotero] Error converting item: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return None

    def _build_zotero_url(self, item_key: str) -> str:
        """Build Zotero web URL for an item using username (not user_id)"""
        # Zotero web URLs use username, not numeric user_id
        username = self.config.credentials.get('username')
        user_id = self.config.credentials.get('user_id')

        if username:
            # Primary format: https://www.zotero.org/{username}/items/{item_key}
            return f"https://www.zotero.org/{username}/items/{item_key}"
        elif user_id:
            # Fallback to user_id format (less reliable for web viewing)
            return f"https://www.zotero.org/users/{user_id}/items/{item_key}"
        else:
            # Last resort: just use the item key
            return f"https://www.zotero.org/items/{item_key}"

    async def _get_pdf_content(self, item_key: str) -> str:
        """Download and extract text from PDF attachment - NO LIMITS"""
        if not PYPDF2_AVAILABLE:
            print(f"[Zotero] PyPDF2 not available, skipping PDF extraction", flush=True)
            return ""

        try:
            # Get children (attachments) of this item
            children = self.zot.children(item_key)
            print(f"[Zotero] Item {item_key} has {len(children)} children", flush=True)

            for child in children:
                child_data = child.get('data', {})
                content_type = child_data.get('contentType', '')
                filename = child_data.get('filename', 'unknown')

                print(f"[Zotero] Child attachment: {filename}, type={content_type}", flush=True)

                if content_type == 'application/pdf':
                    attachment_key = child_data.get('key')

                    try:
                        # Download the PDF file
                        print(f"[Zotero] Downloading PDF: {filename}", flush=True)
                        pdf_bytes = self.zot.file(attachment_key)
                        print(f"[Zotero] Downloaded {len(pdf_bytes)} bytes", flush=True)

                        # Extract text from PDF - NO LIMITS
                        text = self._extract_pdf_text(pdf_bytes, filename)
                        if text:
                            print(f"[Zotero] Extracted {len(text)} chars from {filename}", flush=True)
                            return text  # Return full content, no limit

                    except Exception as e:
                        print(f"[Zotero] Failed to download/extract PDF {filename}: {e}", flush=True)
                        import traceback
                        traceback.print_exc()
                        continue

            return ""

        except Exception as e:
            print(f"[Zotero] Error getting PDF content: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return ""

    def _extract_pdf_text(self, pdf_bytes: bytes, filename: str = "document.pdf") -> str:
        """Extract text from PDF bytes. Tries Mistral Document AI first, falls back to PyPDF2."""
        # Try Mistral Document AI first
        try:
            from parsers.document_parser import DocumentParser
            parser = DocumentParser()
            parsed = parser.parse_file_bytes(pdf_bytes, filename)
            if parsed:
                print(f"[Zotero] Parsed PDF with Mistral Document AI: {len(parsed)} chars", flush=True)
                return parsed
        except Exception as e:
            print(f"[Zotero] Mistral unavailable, falling back to PyPDF2: {e}", flush=True)

        # Fallback to PyPDF2
        if not PYPDF2_AVAILABLE:
            return ""

        try:
            pdf_file = io.BytesIO(pdf_bytes)
            reader = PyPDF2.PdfReader(pdf_file)

            text_parts = []
            for page in reader.pages:
                try:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
                except Exception:
                    continue

            return '\n'.join(text_parts)

        except Exception as e:
            print(f"[Zotero] PDF extraction error: {e}", flush=True)
            return ""

    def get_library_stats(self) -> Dict[str, Any]:
        """Get statistics about the Zotero library"""
        if not self.zot:
            return {}

        try:
            return {
                "total_items": self.zot.num_items(),
                "library_version": self.config.settings.get("library_version"),
                "last_sync": self.config.last_sync.isoformat() if self.config.last_sync else None
            }
        except Exception as e:
            return {"error": str(e)}
