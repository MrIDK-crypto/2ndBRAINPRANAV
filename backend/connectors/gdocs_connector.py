"""
Google Docs Connector for 2nd Brain
Syncs Google Docs documents via Google Drive API
"""

import os
import io
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from urllib.parse import urlencode
import requests

from connectors.base_connector import (
    BaseConnector,
    ConnectorConfig,
    ConnectorStatus,
    Document
)

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    GDOCS_AVAILABLE = True
except ImportError:
    GDOCS_AVAILABLE = False

GDOCS_SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/drive.metadata.readonly'
]

GDOCS_MIME = 'application/vnd.google-apps.document'
EXPORT_MIME = 'text/plain'


class GDocsConnector(BaseConnector):
    """Connector for Google Docs - syncs only Google Docs files"""

    CONNECTOR_TYPE = "gdocs"
    REQUIRED_CREDENTIALS = ["access_token"]
    OPTIONAL_SETTINGS = {
        "folder_ids": [],
        "include_shared": True,
        "max_files": 500
    }

    def __init__(self, config: ConnectorConfig):
        super().__init__(config)
        self.service = None
        self.credentials: Optional[Credentials] = None
        self.user_email: str = ""

    def connect(self) -> bool:
        if not GDOCS_AVAILABLE:
            self._set_error("Google API SDK not installed")
            return False
        try:
            self.status = ConnectorStatus.CONNECTING
            access_token = self.config.credentials.get("access_token")
            refresh_token = self.config.credentials.get("refresh_token")
            if not access_token:
                self._set_error("Missing access_token")
                return False

            self.credentials = Credentials(
                token=access_token,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=os.getenv("GOOGLE_CLIENT_ID"),
                client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
                scopes=GDOCS_SCOPES
            )
            if self.credentials.expired and self.credentials.refresh_token:
                try:
                    self.credentials.refresh(Request())
                    self.config.credentials["access_token"] = self.credentials.token
                except Exception as e:
                    print(f"[GDocs] Token refresh failed: {e}")

            self.service = build('drive', 'v3', credentials=self.credentials)
            about = self.service.about().get(fields="user").execute()
            self.user_email = about.get("user", {}).get("emailAddress", "")
            self.status = ConnectorStatus.CONNECTED
            self._clear_error()
            return True
        except Exception as e:
            self._set_error(f"Connection failed: {str(e)}")
            return False

    def disconnect(self) -> bool:
        self.service = None
        self.credentials = None
        self.status = ConnectorStatus.DISCONNECTED
        return True

    def test_connection(self) -> bool:
        if not self.service:
            return False
        try:
            self.service.about().get(fields="user").execute()
            return True
        except Exception:
            return False

    def sync(self, since: Optional[datetime] = None) -> List[Document]:
        if not self.service:
            if not self.connect():
                return []

        self.status = ConnectorStatus.SYNCING
        documents = []
        try:
            max_files = self.config.settings.get("max_files", 500)
            include_shared = self.config.settings.get("include_shared", True)
            folder_ids = self.config.settings.get("folder_ids", [])

            query_parts = [f"mimeType='{GDOCS_MIME}'", "trashed=false"]
            if since:
                query_parts.append(f"modifiedTime > '{since.strftime('%Y-%m-%dT%H:%M:%S')}'")
            if folder_ids:
                folder_queries = [f"'{fid}' in parents" for fid in folder_ids]
                query_parts.append(f"({' or '.join(folder_queries)})")

            query = " and ".join(query_parts)
            page_token = None
            file_count = 0

            while file_count < max_files:
                response = self.service.files().list(
                    q=query, spaces='drive',
                    fields='nextPageToken, files(id, name, mimeType, modifiedTime, createdTime, owners, webViewLink)',
                    pageToken=page_token, pageSize=min(100, max_files - file_count),
                    includeItemsFromAllDrives=include_shared, supportsAllDrives=True
                ).execute()

                for file in response.get('files', []):
                    doc = self._file_to_document(file)
                    if doc:
                        documents.append(doc)
                        file_count += 1
                        if file_count >= max_files:
                            break

                page_token = response.get('nextPageToken')
                if not page_token:
                    break

            self.config.last_sync = datetime.now(timezone.utc)
            self.status = ConnectorStatus.CONNECTED
            print(f"[GDocs] Sync complete: {len(documents)} docs")
        except Exception as e:
            self._set_error(f"Sync failed: {str(e)}")
            import traceback
            traceback.print_exc()
        return documents

    def get_document(self, doc_id: str) -> Optional[Document]:
        if not self.service:
            self.connect()
        try:
            file_id = doc_id.replace("gdocs_", "")
            file = self.service.files().get(
                fileId=file_id,
                fields='id, name, mimeType, modifiedTime, createdTime, owners, webViewLink'
            ).execute()
            return self._file_to_document(file)
        except Exception as e:
            self._set_error(f"Failed to get document: {str(e)}")
            return None

    def _file_to_document(self, file: Dict[str, Any]) -> Optional[Document]:
        try:
            file_id = file['id']
            name = file['name']
            content = self._extract_content(file_id)
            if not content:
                content = f"[Google Doc: {name}]"

            owners = file.get('owners', [])
            owner_names = [o.get('displayName', o.get('emailAddress', '')) for o in owners]
            modified = file.get('modifiedTime', '')
            timestamp = None
            if modified:
                try:
                    timestamp = datetime.fromisoformat(modified.replace('Z', '+00:00'))
                except:
                    pass

            return Document(
                doc_id=f"gdocs_{file_id}",
                source="gdocs",
                content=content,
                title=name,
                metadata={"file_id": file_id, "mime_type": GDOCS_MIME, "owners": owner_names, "user": self.user_email},
                timestamp=timestamp,
                author=owner_names[0] if owner_names else None,
                url=file.get('webViewLink'),
                doc_type="document"
            )
        except Exception as e:
            print(f"[GDocs] Error converting file: {e}")
            return None

    def _extract_content(self, file_id: str) -> Optional[str]:
        try:
            response = self.service.files().export(fileId=file_id, mimeType=EXPORT_MIME).execute()
            if isinstance(response, bytes):
                return response.decode('utf-8', errors='ignore')
            return str(response)
        except Exception as e:
            print(f"[GDocs] Export failed for {file_id}: {e}")
            return None

    @classmethod
    def get_auth_url(cls, redirect_uri: str, state: str) -> str:
        params = {
            'client_id': os.getenv("GOOGLE_CLIENT_ID", ""),
            'redirect_uri': redirect_uri,
            'scope': ' '.join(GDOCS_SCOPES),
            'response_type': 'code',
            'access_type': 'offline',
            'prompt': 'consent',
            'state': state
        }
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

    @classmethod
    def exchange_code(cls, code: str, redirect_uri: str) -> Dict[str, Any]:
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
