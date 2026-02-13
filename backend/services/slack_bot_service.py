"""
Slack Bot Service
Handles Slack bot interactions, commands, and search functionality.
"""

import os
import time
import threading
from typing import Dict, Optional, List
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from database.models import get_db
from services.enhanced_search_service import EnhancedSearchService


# ============================================================================
# TENANT LOOKUP CACHE (Performance optimization)
# ============================================================================
# Cache tenant_id and bot_token lookups to avoid O(n) database queries per request

class WorkspaceCache:
    """TTL cache for Slack workspace -> tenant mappings"""

    def __init__(self, ttl_seconds: int = 3600):  # 1 hour default TTL
        self.ttl = ttl_seconds
        self._tenant_cache: Dict[str, tuple] = {}  # team_id -> (tenant_id, timestamp)
        self._token_cache: Dict[str, tuple] = {}   # team_id -> (bot_token, timestamp)
        self._lock = threading.Lock()

    def get_tenant(self, team_id: str) -> Optional[str]:
        """Get cached tenant_id for team_id, or None if not cached/expired"""
        with self._lock:
            if team_id in self._tenant_cache:
                tenant_id, timestamp = self._tenant_cache[team_id]
                if time.time() - timestamp < self.ttl:
                    return tenant_id
                else:
                    del self._tenant_cache[team_id]  # Expired
        return None

    def set_tenant(self, team_id: str, tenant_id: str):
        """Cache tenant_id for team_id"""
        with self._lock:
            self._tenant_cache[team_id] = (tenant_id, time.time())

    def get_token(self, team_id: str) -> Optional[str]:
        """Get cached bot_token for team_id, or None if not cached/expired"""
        with self._lock:
            if team_id in self._token_cache:
                token, timestamp = self._token_cache[team_id]
                if time.time() - timestamp < self.ttl:
                    return token
                else:
                    del self._token_cache[team_id]  # Expired
        return None

    def set_token(self, team_id: str, token: str):
        """Cache bot_token for team_id"""
        with self._lock:
            self._token_cache[team_id] = (token, time.time())

    def invalidate(self, team_id: str):
        """Invalidate cache for a team_id (call after OAuth or disconnect)"""
        with self._lock:
            self._tenant_cache.pop(team_id, None)
            self._token_cache.pop(team_id, None)


# Singleton cache instance
_workspace_cache = WorkspaceCache()


class SlackBotService:
    """Service for handling Slack bot interactions"""

    def __init__(self, bot_token: str):
        """
        Initialize Slack bot service.

        Args:
            bot_token: Slack bot OAuth token
        """
        self.client = WebClient(token=bot_token)
        self.bot_user_id = None
        self._init_bot_user()

    def _init_bot_user(self):
        """Get bot user ID"""
        try:
            response = self.client.auth_test()
            self.bot_user_id = response['user_id']
            print(f"[SlackBot] Initialized as {response['user']} (ID: {self.bot_user_id})", flush=True)
        except SlackApiError as e:
            print(f"[SlackBot] Error initializing: {e}", flush=True)

    def handle_ask_command(
        self,
        tenant_id: str,
        user_id: str,
        channel_id: str,
        query: str,
        response_url: Optional[str] = None
    ) -> Dict:
        """
        Handle /ask slash command.

        Args:
            tenant_id: Tenant ID from workspace mapping
            user_id: Slack user ID
            channel_id: Slack channel ID
            query: Search query
            response_url: Optional webhook URL for delayed response

        Returns:
            dict: Slack message response
        """
        try:
            # Show immediate "searching..." message
            if response_url:
                self._send_ephemeral_message(
                    channel_id,
                    user_id,
                    "🔍 Searching knowledge base..."
                )

            # Perform search using EnhancedSearchService with Pinecone
            try:
                from vector_stores.pinecone_store import get_vector_store

                search_service = EnhancedSearchService()
                vector_store = get_vector_store()

                print(f"[SlackBot] Searching for: {query} (tenant: {tenant_id})", flush=True)

                result = search_service.search_and_answer(
                    query=query,
                    tenant_id=tenant_id,
                    vector_store=vector_store,
                    top_k=5
                )

                print(f"[SlackBot] Search result: answer_len={len(result.get('answer', ''))}, sources={result.get('num_sources', 0)}", flush=True)

                # Format response for Slack
                if result.get('answer') and 'Error' not in result['answer']:
                    return {
                        'response_type': 'in_channel',  # Visible to everyone
                        'blocks': self._format_search_results(query, {
                            'answer': result['answer'],
                            'sources': result.get('sources', []),
                            'hallucination_check': result.get('hallucination_check'),
                            'success': True
                        })
                    }
                else:
                    return {
                        'response_type': 'ephemeral',  # Only visible to user
                        'text': f"❌ No results found for: _{query}_\n\nTry:\n• Adding more documents to your knowledge base\n• Using different keywords\n• Checking if documents are indexed"
                    }

            except Exception as e:
                import traceback
                print(f"[SlackBot] Search error: {e}", flush=True)
                traceback.print_exc()
                raise

        except Exception as e:
            print(f"[SlackBot] Error handling /ask: {e}", flush=True)
            return {
                'response_type': 'ephemeral',
                'text': f"❌ Error searching: {str(e)}"
            }

    def handle_app_mention(
        self,
        tenant_id: str,
        event: Dict
    ) -> Optional[Dict]:
        """
        Handle @2ndBrain mentions in channels.

        Args:
            tenant_id: Tenant ID
            event: Slack event data

        Returns:
            Optional response dict
        """
        try:
            import re
            channel = event.get('channel')
            user = event.get('user')
            text = event.get('text', '')

            print(f"[SlackBot] handle_app_mention called: channel={channel}, text={text[:100]}", flush=True)

            # Remove ALL bot mentions from text (more robust than specific bot_user_id)
            # Matches patterns like <@U12345678>
            query = re.sub(r'<@[A-Z0-9]+>', '', text).strip()

            if not query:
                return {
                    'channel': channel,
                    'text': "Hi! 👋 Ask me a question about your knowledge base. Example: `@2ndBrain What is our pricing model?`"
                }

            # Perform search using EnhancedSearchService with Pinecone
            try:
                from vector_stores.pinecone_store import get_vector_store

                search_service = EnhancedSearchService()
                vector_store = get_vector_store()

                print(f"[SlackBot] App mention search: {query} (tenant: {tenant_id})", flush=True)

                result = search_service.search_and_answer(
                    query=query,
                    tenant_id=tenant_id,
                    vector_store=vector_store,
                    top_k=5
                )

                print(f"[SlackBot] Search result: sources={result.get('num_sources', 0)}", flush=True)

                if result.get('answer') and 'Error' not in result['answer']:
                    # Post result in thread (compact=False to show sources with hyperlinks)
                    blocks = self._format_search_results(query, {
                        'answer': result['answer'],
                        'sources': result.get('sources', []),
                        'hallucination_check': result.get('hallucination_check'),
                        'success': True
                    }, compact=False)

                    self.client.chat_postMessage(
                        channel=channel,
                        text=result['answer'][:100] + '...',  # Fallback text
                        blocks=blocks,
                        thread_ts=event.get('ts')  # Reply in thread
                    )
                else:
                    self.client.chat_postMessage(
                        channel=channel,
                        text=f"❌ No results found for: _{query}_",
                        thread_ts=event.get('ts')
                    )

            except Exception as e:
                import traceback
                print(f"[SlackBot] App mention error: {e}", flush=True)
                traceback.print_exc()
                self.client.chat_postMessage(
                    channel=channel,
                    text=f"❌ Error searching: {str(e)}",
                    thread_ts=event.get('ts')
                )

        except Exception as e:
            print(f"[SlackBot] Error handling mention: {e}", flush=True)
            return None

    def handle_message(
        self,
        tenant_id: str,
        event: Dict
    ) -> Optional[Dict]:
        """
        Handle direct messages to bot.

        Args:
            tenant_id: Tenant ID
            event: Slack event data

        Returns:
            Optional response
        """
        try:
            channel = event.get('channel')
            user = event.get('user')
            text = event.get('text', '').strip()

            print(f"[SlackBot] handle_message called: channel={channel}, user={user}, text={text[:50] if text else 'empty'}", flush=True)

            # Ignore bot messages
            if event.get('bot_id') or user == self.bot_user_id:
                print(f"[SlackBot] Ignoring bot message", flush=True)
                return None

            # Check if it's a DM (channel starts with 'D')
            if not channel.startswith('D'):
                print(f"[SlackBot] Not a DM, ignoring", flush=True)
                return None  # Only handle DMs here

            if not text:
                print(f"[SlackBot] Empty text, ignoring", flush=True)
                return None

            # Perform search using EnhancedSearchService with Pinecone
            try:
                from vector_stores.pinecone_store import get_vector_store

                search_service = EnhancedSearchService()
                vector_store = get_vector_store()

                print(f"[SlackBot] DM search: {text} (tenant: {tenant_id})", flush=True)

                result = search_service.search_and_answer(
                    query=text,
                    tenant_id=tenant_id,
                    vector_store=vector_store,
                    top_k=5
                )

                print(f"[SlackBot] Search result: sources={result.get('num_sources', 0)}", flush=True)

                if result.get('answer') and 'Error' not in result['answer']:
                    blocks = self._format_search_results(text, {
                        'answer': result['answer'],
                        'sources': result.get('sources', []),
                        'hallucination_check': result.get('hallucination_check'),
                        'success': True
                    }, compact=False)

                    self.client.chat_postMessage(
                        channel=channel,
                        text=result['answer'][:100] + '...',
                        blocks=blocks
                    )
                else:
                    self.client.chat_postMessage(
                        channel=channel,
                        text=f"❌ No results found for: _{text}_"
                    )

            except Exception as e:
                import traceback
                print(f"[SlackBot] DM error: {e}", flush=True)
                traceback.print_exc()
                self.client.chat_postMessage(
                    channel=channel,
                    text=f"❌ Error searching: {str(e)}"
                )

        except Exception as e:
            print(f"[SlackBot] Error handling message: {e}", flush=True)
            return None

    def _format_search_results(
        self,
        query: str,
        result: Dict,
        compact: bool = False
    ) -> List[Dict]:
        """
        Format search results as Slack blocks.

        Args:
            query: Original query
            result: Search result from EnhancedSearchService
            compact: If True, use compact format

        Returns:
            list: Slack block kit blocks
        """
        blocks = []

        # Header
        blocks.append({
            'type': 'section',
            'text': {
                'type': 'mrkdwn',
                'text': f"*🔍 Results for:* _{query}_"
            }
        })

        blocks.append({'type': 'divider'})

        # Answer
        answer = result.get('answer', 'No answer available')
        answer_chunks = self._chunk_text(answer, 3000)  # Slack limit

        for chunk in answer_chunks:
            blocks.append({
                'type': 'section',
                'text': {
                    'type': 'mrkdwn',
                    'text': chunk
                }
            })

        # Sources (if not compact) - with working hyperlinks where possible
        if not compact and result.get('sources'):
            blocks.append({'type': 'divider'})

            # DEBUG: Log first source structure to diagnose deep link issues
            if result['sources']:
                first_src = result['sources'][0]
                print(f"[SlackBot] DEBUG Source keys: {list(first_src.keys())}", flush=True)
                print(f"[SlackBot] DEBUG metadata: {first_src.get('metadata', {})}", flush=True)

            sources_text = "*📚 Sources:*\n"
            for idx, source in enumerate(result['sources'][:5], 1):
                # Get title - try multiple locations
                title = source.get('title', '') or source.get('metadata', {}).get('title', '') or 'Untitled'

                # Get metadata for source_type and Slack deep link info
                metadata = source.get('metadata', {})
                source_type = metadata.get('source_type', '') or source.get('source_type', '') or 'document'
                external_id = metadata.get('external_id', '') or source.get('external_id', '')

                # Slack deep link metadata
                team_domain = metadata.get('team_domain', '')
                channel_id = metadata.get('channel_id', '')
                message_ts = metadata.get('message_ts', '')

                # Clean up title - remove redundant source prefix if present
                display_title = title
                if source_type == 'slack' and display_title.lower().startswith('slack:'):
                    display_title = display_title[6:].strip()
                elif source_type == 'gmail' and display_title.lower().startswith('gmail:'):
                    display_title = display_title[6:].strip()

                # Truncate long titles for Slack display
                if len(display_title) > 70:
                    display_title = display_title[:67] + "..."

                # Create hyperlinks based on source type
                if source_type == 'gmail' and external_id:
                    # Gmail messages - link directly to Gmail
                    gmail_link = f"https://mail.google.com/mail/u/0/#inbox/{external_id}"
                    sources_text += f"{idx}. <{gmail_link}|{display_title}> _(Email)_\n"
                elif source_type == 'slack' and team_domain and channel_id and message_ts:
                    # Slack messages - create deep link
                    # Format: https://workspace.slack.com/archives/CHANNEL_ID/pMESSAGE_TS_WITHOUT_DOT
                    ts_no_dot = message_ts.replace('.', '')
                    slack_link = f"https://{team_domain}.slack.com/archives/{channel_id}/p{ts_no_dot}"
                    sources_text += f"{idx}. <{slack_link}|{display_title}> _(Slack)_\n"
                elif source_type == 'slack':
                    # Slack messages without deep link info - plain text
                    sources_text += f"{idx}. {display_title} _(Slack)_\n"
                else:
                    # Other sources - plain text
                    sources_text += f"{idx}. {display_title}\n"

            blocks.append({
                'type': 'section',
                'text': {
                    'type': 'mrkdwn',
                    'text': sources_text
                }
            })

        return blocks

    def _chunk_text(self, text: str, max_length: int = 3000) -> List[str]:
        """
        Chunk text to fit Slack message limits.

        Args:
            text: Text to chunk
            max_length: Maximum length per chunk

        Returns:
            list: Text chunks
        """
        if len(text) <= max_length:
            return [text]

        chunks = []
        current_chunk = ""

        for paragraph in text.split('\n'):
            if len(current_chunk) + len(paragraph) + 1 > max_length:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = paragraph
            else:
                current_chunk += '\n' + paragraph if current_chunk else paragraph

        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def _send_ephemeral_message(self, channel: str, user: str, text: str):
        """Send ephemeral message (only visible to user)"""
        try:
            self.client.chat_postEphemeral(
                channel=channel,
                user=user,
                text=text
            )
        except SlackApiError as e:
            print(f"[SlackBot] Error sending ephemeral: {e}", flush=True)

    def send_notification(
        self,
        channel: str,
        message: str,
        blocks: Optional[List[Dict]] = None
    ):
        """
        Send notification to Slack channel.

        Args:
            channel: Channel ID
            message: Text message
            blocks: Optional Slack blocks
        """
        try:
            self.client.chat_postMessage(
                channel=channel,
                text=message,
                blocks=blocks
            )
        except SlackApiError as e:
            print(f"[SlackBot] Error sending notification: {e}", flush=True)


# ============================================================================
# SLACK WORKSPACE MAPPING - Uses PostgreSQL database for persistence
# ============================================================================


def register_slack_workspace(team_id: str, tenant_id: str, bot_token: str):
    """
    Register Slack workspace after OAuth.
    This is now handled by the Connector model during OAuth callback.

    Args:
        team_id: Slack workspace/team ID
        tenant_id: 2nd Brain tenant ID
        bot_token: Bot OAuth token
    """
    print(f"[SlackBot] Workspace registration handled by Connector model: {team_id} -> tenant {tenant_id}", flush=True)


def get_tenant_for_workspace(team_id: str) -> Optional[str]:
    """
    Get tenant ID for Slack workspace with caching.

    Args:
        team_id: Slack workspace/team ID

    Returns:
        Optional tenant ID
    """
    if not team_id:
        print("[SlackBot] get_tenant_for_workspace called with empty team_id", flush=True)
        return None

    # Check cache first (O(1) instead of O(n))
    cached = _workspace_cache.get_tenant(team_id)
    if cached:
        print(f"[SlackBot] Cache HIT: tenant {cached[:8]}... for workspace {team_id}", flush=True)
        return cached

    try:
        from database.models import Connector, ConnectorType

        db = next(get_db())
        try:
            # Get all active Slack connectors and filter in Python
            connectors = db.query(Connector).filter(
                Connector.connector_type == ConnectorType.SLACK,
                Connector.is_active == True
            ).all()

            print(f"[SlackBot] Cache MISS: Querying {len(connectors)} Slack connectors", flush=True)

            for connector in connectors:
                settings = connector.settings or {}
                connector_team_id = settings.get('team_id')

                if connector_team_id == team_id:
                    tenant_id = connector.tenant_id
                    # Cache the result for future requests
                    _workspace_cache.set_tenant(team_id, tenant_id)
                    print(f"[SlackBot] Found and cached tenant {tenant_id[:8]}... for workspace {team_id}", flush=True)
                    return tenant_id

            print(f"[SlackBot] No connector found for workspace {team_id}", flush=True)
            return None

        finally:
            db.close()

    except Exception as e:
        import traceback
        print(f"[SlackBot] Error looking up tenant for workspace {team_id}: {e}", flush=True)
        traceback.print_exc()
        return None


def get_bot_token_for_workspace(team_id: str) -> Optional[str]:
    """
    Get bot token for Slack workspace with caching.

    Args:
        team_id: Slack workspace/team ID

    Returns:
        Optional bot token
    """
    if not team_id:
        print("[SlackBot] get_bot_token_for_workspace called with empty team_id", flush=True)
        return None

    # Check cache first (O(1) instead of O(n))
    cached = _workspace_cache.get_token(team_id)
    if cached:
        print(f"[SlackBot] Cache HIT: bot token for workspace {team_id}", flush=True)
        return cached

    try:
        from database.models import Connector, ConnectorType

        db = next(get_db())
        try:
            # Get all active Slack connectors and filter in Python
            connectors = db.query(Connector).filter(
                Connector.connector_type == ConnectorType.SLACK,
                Connector.is_active == True
            ).all()

            print(f"[SlackBot] Cache MISS: Querying {len(connectors)} connectors for token", flush=True)

            for connector in connectors:
                settings = connector.settings or {}
                connector_team_id = settings.get('team_id')

                if connector_team_id == team_id and connector.access_token:
                    # Cache the token for future requests
                    _workspace_cache.set_token(team_id, connector.access_token)
                    print(f"[SlackBot] Found and cached bot token for workspace {team_id}", flush=True)
                    return connector.access_token

            print(f"[SlackBot] No bot token found for workspace {team_id}, using fallback", flush=True)
            # Fallback to environment variable
            return os.getenv('SLACK_BOT_TOKEN')

        finally:
            db.close()

    except Exception as e:
        import traceback
        print(f"[SlackBot] Error looking up bot token for workspace {team_id}: {e}", flush=True)
        traceback.print_exc()
        # Fallback to environment variable
        return os.getenv('SLACK_BOT_TOKEN')
