"""
Connector Manager
Manages all data source connectors for knowledge capture.
"""

import json
import pickle
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Type
import asyncio

from .base_connector import BaseConnector, ConnectorConfig, ConnectorStatus, Document
from .gmail_connector import GmailConnector
from .slack_connector import SlackConnector
from .github_connector import GitHubConnector


class ConnectorManager:
    """
    Manages multiple data source connectors.

    Features:
    - Register and configure connectors
    - Unified sync across all sources
    - OAuth flow management
    - Status monitoring
    - Document aggregation
    """

    # Available connector types
    CONNECTOR_TYPES: Dict[str, Type[BaseConnector]] = {
        "gmail": GmailConnector,
        "slack": SlackConnector,
        "github": GitHubConnector
    }

    def __init__(self, config_dir: Path = None):
        self.config_dir = config_dir or Path("./connector_configs")
        self.config_dir.mkdir(exist_ok=True)

        self.connectors: Dict[str, BaseConnector] = {}  # user_id_type -> connector
        self.sync_history: List[Dict] = []

    def get_connector_id(self, user_id: str, connector_type: str) -> str:
        """Generate unique connector ID"""
        return f"{user_id}_{connector_type}"

    def get_available_connectors(self) -> List[Dict]:
        """Get list of available connector types"""
        return [
            {
                "type": "gmail",
                "name": "Gmail",
                "description": "Sync emails from your Gmail account",
                "icon": "mail",
                "auth_type": "oauth",
                "required_scopes": GmailConnector.SCOPES
            },
            {
                "type": "slack",
                "name": "Slack",
                "description": "Sync messages from Slack workspaces",
                "icon": "slack",
                "auth_type": "token",
                "required_scopes": ["channels:history", "users:read"]
            },
            {
                "type": "github",
                "name": "GitHub",
                "description": "Sync code, issues, and PRs from GitHub repos",
                "icon": "github",
                "auth_type": "token",
                "required_scopes": ["repo", "read:user"]
            },
            {
                "type": "google_drive",
                "name": "Google Drive",
                "description": "Sync documents from Google Drive",
                "icon": "drive",
                "auth_type": "oauth",
                "available": False,
                "coming_soon": True
            },
            {
                "type": "notion",
                "name": "Notion",
                "description": "Sync pages and databases from Notion",
                "icon": "notion",
                "auth_type": "oauth",
                "available": False,
                "coming_soon": True
            },
            {
                "type": "confluence",
                "name": "Confluence",
                "description": "Sync pages from Atlassian Confluence",
                "icon": "confluence",
                "auth_type": "oauth",
                "available": False,
                "coming_soon": True
            }
        ]

    async def add_connector(
        self,
        user_id: str,
        connector_type: str,
        credentials: Dict,
        settings: Dict = None
    ) -> Dict:
        """Add a new connector for a user"""
        if connector_type not in self.CONNECTOR_TYPES:
            return {"success": False, "error": f"Unknown connector type: {connector_type}"}

        connector_id = self.get_connector_id(user_id, connector_type)

        # Create config
        config = ConnectorConfig(
            connector_type=connector_type,
            user_id=user_id,
            credentials=credentials,
            settings=settings or {}
        )

        # Create connector instance
        connector_class = self.CONNECTOR_TYPES[connector_type]
        connector = connector_class(config)

        # Validate credentials
        if not connector.validate_credentials():
            return {
                "success": False,
                "error": f"Missing required credentials: {connector_class.REQUIRED_CREDENTIALS}"
            }

        # Try to connect
        connected = await connector.connect()
        if not connected:
            return {
                "success": False,
                "error": connector.last_error or "Failed to connect"
            }

        # Store connector
        self.connectors[connector_id] = connector

        # Save config
        self._save_config(connector_id, config)

        return {
            "success": True,
            "connector_id": connector_id,
            "status": connector.get_status()
        }

    async def remove_connector(self, user_id: str, connector_type: str) -> bool:
        """Remove a connector"""
        connector_id = self.get_connector_id(user_id, connector_type)

        if connector_id in self.connectors:
            await self.connectors[connector_id].disconnect()
            del self.connectors[connector_id]

        # Remove config file
        config_file = self.config_dir / f"{connector_id}.json"
        if config_file.exists():
            config_file.unlink()

        return True

    def get_user_connectors(self, user_id: str) -> List[Dict]:
        """Get all connectors for a user"""
        user_connectors = []

        for connector_id, connector in self.connectors.items():
            if connector.config.user_id == user_id:
                user_connectors.append(connector.get_status())

        return user_connectors

    async def sync_connector(
        self,
        user_id: str,
        connector_type: str,
        since: Optional[datetime] = None
    ) -> Dict:
        """Sync documents from a specific connector"""
        connector_id = self.get_connector_id(user_id, connector_type)

        if connector_id not in self.connectors:
            return {"success": False, "error": "Connector not found"}

        connector = self.connectors[connector_id]

        try:
            documents = await connector.sync(since)

            # Update config with last sync time
            connector.config.last_sync = datetime.now()
            self._save_config(connector_id, connector.config)

            # Record sync history
            self.sync_history.append({
                "connector_id": connector_id,
                "user_id": user_id,
                "connector_type": connector_type,
                "timestamp": datetime.now().isoformat(),
                "documents_synced": len(documents),
                "success": True
            })

            return {
                "success": True,
                "documents": [doc.to_dict() for doc in documents],
                "count": len(documents),
                "sync_time": datetime.now().isoformat()
            }

        except Exception as e:
            self.sync_history.append({
                "connector_id": connector_id,
                "user_id": user_id,
                "connector_type": connector_type,
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "success": False
            })

            return {"success": False, "error": str(e)}

    async def sync_all(self, user_id: str, since: Optional[datetime] = None) -> Dict:
        """Sync all connectors for a user"""
        results = {}
        all_documents = []

        for connector_id, connector in self.connectors.items():
            if connector.config.user_id == user_id and connector.config.enabled:
                result = await self.sync_connector(
                    user_id,
                    connector.config.connector_type,
                    since
                )
                results[connector.config.connector_type] = result

                if result.get("success") and result.get("documents"):
                    all_documents.extend(result["documents"])

        return {
            "success": True,
            "results": results,
            "total_documents": len(all_documents),
            "documents": all_documents
        }

    def get_auth_url(self, connector_type: str, redirect_uri: str, state: str) -> str:
        """Get OAuth authorization URL for a connector type"""
        if connector_type not in self.CONNECTOR_TYPES:
            raise ValueError(f"Unknown connector type: {connector_type}")

        connector_class = self.CONNECTOR_TYPES[connector_type]
        return connector_class.get_auth_url(redirect_uri, state)

    async def handle_oauth_callback(
        self,
        connector_type: str,
        code: str,
        redirect_uri: str,
        user_id: str,
        settings: Dict = None
    ) -> Dict:
        """Handle OAuth callback and create connector"""
        if connector_type not in self.CONNECTOR_TYPES:
            return {"success": False, "error": f"Unknown connector type: {connector_type}"}

        try:
            connector_class = self.CONNECTOR_TYPES[connector_type]
            credentials = await connector_class.exchange_code(code, redirect_uri)

            return await self.add_connector(
                user_id=user_id,
                connector_type=connector_type,
                credentials=credentials,
                settings=settings
            )

        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_all_status(self, user_id: str = None) -> Dict:
        """Get status of all connectors"""
        statuses = {}

        for connector_id, connector in self.connectors.items():
            if user_id is None or connector.config.user_id == user_id:
                statuses[connector_id] = connector.get_status()

        return {
            "connectors": statuses,
            "total_connected": sum(
                1 for s in statuses.values()
                if s["status"] == ConnectorStatus.CONNECTED.value
            ),
            "total_configured": len(statuses)
        }

    def _save_config(self, connector_id: str, config: ConnectorConfig):
        """Save connector config to file"""
        config_file = self.config_dir / f"{connector_id}.json"

        # Don't save sensitive credentials directly
        safe_config = config.to_dict()

        with open(config_file, 'w') as f:
            json.dump(safe_config, f, indent=2)

    def _load_config(self, connector_id: str) -> Optional[ConnectorConfig]:
        """Load connector config from file"""
        config_file = self.config_dir / f"{connector_id}.json"

        if not config_file.exists():
            return None

        with open(config_file, 'r') as f:
            data = json.load(f)

        return ConnectorConfig.from_dict(data)

    async def load_saved_connectors(self):
        """Load all saved connector configs and connect"""
        for config_file in self.config_dir.glob("*.json"):
            try:
                with open(config_file, 'r') as f:
                    data = json.load(f)

                config = ConnectorConfig.from_dict(data)
                connector_id = self.get_connector_id(config.user_id, config.connector_type)

                if config.connector_type in self.CONNECTOR_TYPES:
                    connector_class = self.CONNECTOR_TYPES[config.connector_type]
                    connector = connector_class(config)

                    if config.enabled:
                        await connector.connect()

                    self.connectors[connector_id] = connector

            except Exception as e:
                print(f"Error loading connector config {config_file}: {e}")


# Global connector manager instance
connector_manager = ConnectorManager()


async def init_connector_manager():
    """Initialize the connector manager"""
    await connector_manager.load_saved_connectors()
    return connector_manager
