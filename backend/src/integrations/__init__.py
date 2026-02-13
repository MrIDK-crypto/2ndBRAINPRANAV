"""
API Connectors Module
Provides integration with external data sources like Gmail, Slack, GitHub, etc.
for comprehensive knowledge capture.
"""

from .base_connector import BaseConnector, ConnectorConfig, Document
from .gmail_connector import GmailConnector
from .slack_connector import SlackConnector
from .github_connector import GitHubConnector
from .connector_manager import ConnectorManager

__all__ = [
    'BaseConnector',
    'ConnectorConfig',
    'Document',
    'GmailConnector',
    'SlackConnector',
    'GitHubConnector',
    'ConnectorManager'
]
