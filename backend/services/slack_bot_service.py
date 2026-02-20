"""
Slack Bot Service
Handles Slack bot interactions, commands, and search functionality.
"""

import os
import re
import time
import threading
from collections import defaultdict
from typing import Dict, Optional, List
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from database.models import get_db, AuditLog, SessionLocal
from services.enhanced_search_service import EnhancedSearchService


def _log_slack_query(tenant_id: str, query: str, result: str, channel_type: str):
    """Log a Slack bot query to AuditLog for analytics tracking.
    result: 'answered' or 'no_results'
    channel_type: 'command', 'mention', or 'dm'
    """
    try:
        db = SessionLocal()
        audit = AuditLog(
            tenant_id=tenant_id,
            user_id=None,
            action='slack_bot:question',
            resource_type='slack_bot',
            resource_id=None,
            details={
                'query': query[:500],
                'result': result,
                'channel_type': channel_type,
            },
        )
        db.add(audit)
        db.commit()
        db.close()
    except Exception as e:
        print(f"[SlackBot] Error logging query: {e}", flush=True)


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


# ============================================================================
# CONVERSATION HISTORY CACHE (Per-channel/DM memory for follow-ups)
# ============================================================================

class ConversationCache:
    """
    Thread-safe in-memory conversation history for Slack bot.
    Keys are (tenant_id, channel_id) tuples so conversations are isolated per channel.
    DMs get per-user history, channels get per-thread history.
    """

    MAX_MESSAGES = 20        # Max messages to keep per conversation
    MAX_MSG_LENGTH = 500     # Max chars per message stored
    TTL_SECONDS = 1800       # 30 min TTL per conversation

    def __init__(self):
        self._store: Dict[str, List[Dict]] = {}  # key -> [{role, content, ts}]
        self._timestamps: Dict[str, float] = {}  # key -> last_activity
        self._lock = threading.Lock()

    def _make_key(self, tenant_id: str, channel_id: str, thread_ts: str = None) -> str:
        """Create a cache key. Use thread_ts for threaded channel conversations."""
        if thread_ts:
            return f"{tenant_id}:{channel_id}:{thread_ts}"
        return f"{tenant_id}:{channel_id}"

    def add_message(self, tenant_id: str, channel_id: str, role: str, content: str, thread_ts: str = None):
        """Add a message to conversation history."""
        key = self._make_key(tenant_id, channel_id, thread_ts)
        truncated = content[:self.MAX_MSG_LENGTH] if content else ""

        with self._lock:
            self._cleanup_expired()
            if key not in self._store:
                self._store[key] = []
            self._store[key].append({'role': role, 'content': truncated})
            # Trim to max
            if len(self._store[key]) > self.MAX_MESSAGES:
                self._store[key] = self._store[key][-self.MAX_MESSAGES:]
            self._timestamps[key] = time.time()

    def get_history(self, tenant_id: str, channel_id: str, thread_ts: str = None) -> List[Dict]:
        """Get conversation history for a channel/thread."""
        key = self._make_key(tenant_id, channel_id, thread_ts)
        with self._lock:
            ts = self._timestamps.get(key, 0)
            if time.time() - ts > self.TTL_SECONDS:
                self._store.pop(key, None)
                self._timestamps.pop(key, None)
                return []
            return list(self._store.get(key, []))

    def _cleanup_expired(self):
        """Remove expired conversations (called within lock)."""
        now = time.time()
        expired = [k for k, ts in self._timestamps.items() if now - ts > self.TTL_SECONDS]
        for k in expired:
            self._store.pop(k, None)
            self._timestamps.pop(k, None)


# Singleton conversation cache
_conversation_cache = ConversationCache()


# ============================================================================
# MARKDOWN → SLACK MRKDWN CONVERTER
# ============================================================================

def markdown_to_slack(text: str) -> str:
    """
    Convert standard Markdown to Slack mrkdwn format.
    Handles headers, bold, tables, dividers, links, and blockquotes.
    """
    # Strip trailing "Sources Used: [...]" line (we show sources separately)
    text = re.sub(r'\n*Sources?\s*Used:?\s*\[?[\d,\s\[\]Source]*\]?\.?\s*$', '', text, flags=re.IGNORECASE)

    # Protect existing Slack <url|text> links from being mangled by table detection
    # The | in <https://example.com|Title> would be treated as a table cell separator
    _protected_links = []
    def _save_link(match):
        _protected_links.append(match.group(0))
        return f"__SLACKLINK_{len(_protected_links)-1}__"
    text = re.sub(r'<https?://[^>]+\|[^>]+>', _save_link, text)

    lines = text.split('\n')
    converted = []
    in_table = False
    table_headers = []

    for line in lines:
        stripped = line.strip()

        # Skip horizontal rules and unicode dividers
        if re.match(r'^[-─━═]{3,}$', stripped) or re.match(r'^\*{3,}$', stripped):
            continue

        # Skip table separator rows (|---|---|)
        if re.match(r'^\|[\s\-:]+\|', stripped):
            continue

        # Handle table header row
        if stripped.startswith('|') and stripped.endswith('|') and not in_table:
            cells = [c.strip() for c in stripped.strip('|').split('|') if c.strip()]
            if cells:
                table_headers = cells
                in_table = True
            continue

        # Handle table data rows -> convert to bullet points
        if stripped.startswith('|') and stripped.endswith('|') and in_table:
            cells = [c.strip() for c in stripped.strip('|').split('|') if c.strip()]
            if cells and table_headers:
                parts = []
                for i, cell in enumerate(cells):
                    if cell and cell != '-' and cell != 'N/A':
                        header = table_headers[i] if i < len(table_headers) else ''
                        if header and header != cell:
                            parts.append(f"{header}: {cell}")
                        else:
                            parts.append(cell)
                if parts:
                    converted.append(f"• {' | '.join(parts)}")
            continue

        # End of table
        if in_table and not stripped.startswith('|'):
            in_table = False
            table_headers = []

        # Convert headers to bold
        if stripped.startswith('### '):
            line = f"\n*{stripped[4:].strip()}*"
        elif stripped.startswith('## '):
            line = f"\n*{stripped[3:].strip()}*"
        elif stripped.startswith('# '):
            line = f"\n*{stripped[2:].strip()}*"
        else:
            # Convert **bold** to *bold*
            line = re.sub(r'\*\*(.+?)\*\*', r'*\1*', line)

        # Convert [text](url) to <url|text>
        line = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<\2|\1>', line)

        converted.append(line)

    result = '\n'.join(converted)

    # Clean up excessive blank lines
    result = re.sub(r'\n{3,}', '\n\n', result)

    # Restore protected Slack links
    for i, link in enumerate(_protected_links):
        result = result.replace(f"__SLACKLINK_{i}__", link)

    return result.strip()


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

    def _add_reaction(self, channel: str, timestamp: str, emoji: str = "brain"):
        """Add a reaction emoji to a message. Fails silently."""
        try:
            self.client.reactions_add(channel=channel, timestamp=timestamp, name=emoji)
        except SlackApiError as e:
            print(f"[SlackBot] Reaction add error: {e.response.get('error', e)}", flush=True)
        except Exception as e:
            print(f"[SlackBot] Reaction error: {e}", flush=True)

    def _remove_reaction(self, channel: str, timestamp: str, emoji: str = "brain"):
        """Remove a reaction emoji from a message. Fails silently."""
        try:
            self.client.reactions_remove(channel=channel, timestamp=timestamp, name=emoji)
        except SlackApiError as e:
            print(f"[SlackBot] Reaction remove error: {e.response.get('error', e)}", flush=True)
        except Exception as e:
            print(f"[SlackBot] Reaction error: {e}", flush=True)

    def _post_message_safe(self, channel: str, text: str, blocks=None, thread_ts=None):
        """
        Post a message to Slack with auto-join on 'not_in_channel' error.
        Catches and logs all errors instead of raising.
        """
        kwargs = {'channel': channel, 'text': text}
        if blocks:
            kwargs['blocks'] = blocks
        if thread_ts:
            kwargs['thread_ts'] = thread_ts

        try:
            self.client.chat_postMessage(**kwargs)
            print(f"[SlackBot] Message posted to {channel}", flush=True)
        except SlackApiError as e:
            error_code = e.response.get('error', '') if e.response else str(e)
            print(f"[SlackBot] chat_postMessage error: {error_code}", flush=True)

            # If bot isn't in channel, try to join and retry
            if error_code in ('not_in_channel', 'channel_not_found'):
                try:
                    print(f"[SlackBot] Attempting to join channel {channel}...", flush=True)
                    self.client.conversations_join(channel=channel)
                    print(f"[SlackBot] Joined channel {channel}, retrying post...", flush=True)
                    self.client.chat_postMessage(**kwargs)
                    print(f"[SlackBot] Message posted after join", flush=True)
                except SlackApiError as join_err:
                    print(f"[SlackBot] Join+retry failed: {join_err}", flush=True)
            else:
                print(f"[SlackBot] Cannot recover from error: {error_code}", flush=True)
        except Exception as e:
            print(f"[SlackBot] Unexpected post error: {e}", flush=True)

    def _search_knowledge_base(self, query: str, tenant_id: str, conversation_history: list = None) -> Dict:
        """
        Centralized search method used by all handlers.
        Uses the same EnhancedSearchService as the web chatbot.

        Args:
            query: Search query text
            tenant_id: Tenant ID for multi-tenant isolation
            conversation_history: Previous messages for context

        Returns:
            Search result dict from EnhancedSearchService
        """
        from vector_stores.pinecone_store import get_vector_store

        search_service = EnhancedSearchService()
        vector_store = get_vector_store()

        print(f"[SlackBot] Searching: '{query}' (tenant: {tenant_id}, history: {len(conversation_history or [])} msgs)", flush=True)

        result = search_service.search_and_answer(
            query=query,
            tenant_id=tenant_id,
            vector_store=vector_store,
            top_k=10,
            conversation_history=conversation_history
        )

        print(f"[SlackBot] Result: answer_len={len(result.get('answer', ''))}, sources={result.get('num_sources', 0)}", flush=True)
        return result

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
                    "Searching knowledge base..."
                )

            # Get conversation history for this channel
            history = _conversation_cache.get_history(tenant_id, channel_id)

            # Record user query
            _conversation_cache.add_message(tenant_id, channel_id, 'user', query)

            try:
                result = self._search_knowledge_base(query, tenant_id, history)

                # Format response for Slack
                if result.get('answer') and 'Error' not in result['answer']:
                    # Record assistant response
                    _conversation_cache.add_message(tenant_id, channel_id, 'assistant', result['answer'])
                    _log_slack_query(tenant_id, query, 'answered', 'command')

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
                    _log_slack_query(tenant_id, query, 'no_results', 'command')
                    return {
                        'response_type': 'ephemeral',  # Only visible to user
                        'text': f"No results found for: _{query}_\n\nTry:\n- Adding more documents to your knowledge base\n- Using different keywords\n- Checking if documents are indexed"
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
                'text': f"Error searching: {str(e)}"
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
            channel = event.get('channel')
            user = event.get('user')
            text = event.get('text', '')
            thread_ts = event.get('thread_ts') or event.get('ts')

            print(f"[SlackBot] handle_app_mention: channel={channel}, user={user}, text={repr(text[:100])}", flush=True)

            # Remove ALL bot mentions from text
            # Handles both <@U123> and <@U123|displayname> formats
            query = re.sub(r'<@[A-Za-z0-9_]+(?:\|[^>]*)?>', '', text).strip()

            print(f"[SlackBot] Extracted query: {repr(query[:100])}", flush=True)

            if not query:
                self._post_message_safe(
                    channel=channel,
                    text="Hi! Ask me a question about your knowledge base. Example: `@KnowledgeVault What is our pricing model?`",
                    thread_ts=event.get('ts')
                )
                return None

            # Get conversation history for this thread
            history = _conversation_cache.get_history(tenant_id, channel, thread_ts)

            # Record user query
            _conversation_cache.add_message(tenant_id, channel, 'user', query, thread_ts)

            # Add thinking reaction
            message_ts = event.get('ts')
            self._add_reaction(channel, message_ts, "brain")

            try:
                result = self._search_knowledge_base(query, tenant_id, history)

                # Remove thinking reaction
                self._remove_reaction(channel, message_ts, "brain")

                if result.get('answer') and 'Error' not in result['answer']:
                    # Record assistant response
                    _conversation_cache.add_message(tenant_id, channel, 'assistant', result['answer'], thread_ts)
                    _log_slack_query(tenant_id, query, 'answered', 'mention')

                    blocks = self._format_search_results(query, {
                        'answer': result['answer'],
                        'sources': result.get('sources', []),
                        'hallucination_check': result.get('hallucination_check'),
                        'success': True
                    }, compact=False)

                    self._post_message_safe(
                        channel=channel,
                        text=result['answer'][:100] + '...',  # Fallback text
                        blocks=blocks,
                        thread_ts=event.get('ts')  # Reply in thread
                    )
                else:
                    _log_slack_query(tenant_id, query, 'no_results', 'mention')
                    self._post_message_safe(
                        channel=channel,
                        text=f"No results found for: _{query}_",
                        thread_ts=event.get('ts')
                    )

            except Exception as e:
                self._remove_reaction(channel, message_ts, "brain")
                import traceback
                print(f"[SlackBot] App mention search error: {e}", flush=True)
                traceback.print_exc()
                self._post_message_safe(
                    channel=channel,
                    text=f"Sorry, I encountered an error searching: {str(e)[:200]}",
                    thread_ts=event.get('ts')
                )

        except Exception as e:
            import traceback
            print(f"[SlackBot] Error handling mention: {e}", flush=True)
            traceback.print_exc()
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

            print(f"[SlackBot] handle_message: channel={channel}, user={user}, text={text[:50] if text else 'empty'}", flush=True)

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

            # Get conversation history for this DM (keyed by channel = per-user)
            history = _conversation_cache.get_history(tenant_id, channel)

            # Record user query
            _conversation_cache.add_message(tenant_id, channel, 'user', text)

            try:
                result = self._search_knowledge_base(text, tenant_id, history)

                if result.get('answer') and 'Error' not in result['answer']:
                    # Record assistant response
                    _conversation_cache.add_message(tenant_id, channel, 'assistant', result['answer'])
                    _log_slack_query(tenant_id, text, 'answered', 'dm')

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
                    _log_slack_query(tenant_id, text, 'no_results', 'dm')
                    self.client.chat_postMessage(
                        channel=channel,
                        text=f"No results found for: _{text}_"
                    )

            except Exception as e:
                import traceback
                print(f"[SlackBot] DM error: {e}", flush=True)
                traceback.print_exc()
                self.client.chat_postMessage(
                    channel=channel,
                    text=f"Error searching: {str(e)}"
                )

        except Exception as e:
            print(f"[SlackBot] Error handling message: {e}", flush=True)
            return None

    def handle_file_upload(
        self,
        tenant_id: str,
        event: Dict
    ) -> Optional[Dict]:
        """
        Handle file uploads in DMs - index files into the knowledge base.

        Args:
            tenant_id: Tenant ID
            event: Slack event data containing 'files' array
        """
        try:
            channel = event.get('channel')
            user = event.get('user')
            files = event.get('files', [])
            text = event.get('text', '').strip()

            if not files:
                return None

            print(f"[SlackBot] File upload: {len(files)} files from {user}", flush=True)

            indexed_count = 0
            skipped = []

            for file_info in files:
                filename = file_info.get('name', 'unknown')
                filetype = file_info.get('filetype', '')
                url = file_info.get('url_private')
                file_size = file_info.get('size', 0)

                # Skip files that are too large (>25MB)
                if file_size > 25 * 1024 * 1024:
                    skipped.append(f"{filename} (too large)")
                    continue

                # Check if parseable
                import os as _os
                ext = _os.path.splitext(filename)[1].lower()
                parseable = {
                    ".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls",
                    ".txt", ".csv", ".md", ".json", ".xml", ".html", ".htm",
                    ".rtf", ".odt", ".ods", ".odp", ".png", ".jpg", ".jpeg"
                }
                if ext not in parseable:
                    skipped.append(f"{filename} (unsupported type)")
                    continue

                if not url:
                    skipped.append(f"{filename} (no download URL)")
                    continue

                try:
                    # Download file
                    import requests as http_requests
                    token = self.client.token
                    resp = http_requests.get(
                        url,
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=60
                    )
                    resp.raise_for_status()
                    file_bytes = resp.content

                    print(f"[SlackBot] Downloaded {filename}: {len(file_bytes)} bytes", flush=True)

                    # Parse file content
                    from parsers.document_parser import DocumentParser
                    parser = DocumentParser()
                    parsed_content = parser.parse_file_bytes(file_bytes, filename)

                    if not parsed_content:
                        skipped.append(f"{filename} (parse failed)")
                        continue

                    # Store as document in the database
                    from database.models import Document as DBDocument, get_db, DocumentClassification
                    from datetime import datetime, timezone

                    db = next(get_db())
                    try:
                        doc = DBDocument(
                            tenant_id=tenant_id,
                            title=filename,
                            content=parsed_content,
                            source_type='slack_upload',
                            classification=DocumentClassification.WORK,
                            classification_confidence=1.0,
                            user_confirmed=True,
                            metadata={
                                'uploaded_via': 'slack_bot',
                                'uploaded_by': user,
                                'original_filename': filename,
                                'filetype': filetype,
                                'file_size': file_size,
                            },
                            created_at=datetime.now(timezone.utc),
                        )
                        db.add(doc)
                        db.commit()
                        doc_id = doc.id

                        print(f"[SlackBot] Indexed {filename} as doc {doc_id}", flush=True)
                        indexed_count += 1

                        # Trigger embedding in background
                        try:
                            from services.embedding_service import EmbeddingService
                            embedding_svc = EmbeddingService()
                            embedding_svc.embed_documents(tenant_id, [doc_id], db)
                        except Exception as emb_err:
                            print(f"[SlackBot] Embedding error (non-fatal): {emb_err}", flush=True)

                    finally:
                        db.close()

                except Exception as file_err:
                    print(f"[SlackBot] Error processing {filename}: {file_err}", flush=True)
                    skipped.append(f"{filename} (error)")

            # Send confirmation to user
            msg_parts = []
            if indexed_count > 0:
                msg_parts.append(f"Indexed *{indexed_count}* file{'s' if indexed_count > 1 else ''} into your knowledge base.")
            if skipped:
                msg_parts.append(f"Skipped: {', '.join(skipped)}")
            if not msg_parts:
                msg_parts.append("No files could be indexed. Supported: PDF, DOCX, PPTX, XLSX, TXT, CSV, images.")

            self.client.chat_postMessage(
                channel=channel,
                text='\n'.join(msg_parts)
            )

        except Exception as e:
            import traceback
            print(f"[SlackBot] File upload error: {e}", flush=True)
            traceback.print_exc()

    def handle_file_shared(
        self,
        tenant_id: str,
        event: Dict
    ) -> Optional[Dict]:
        """
        Handle file_shared events (fallback for when files arrive without text).
        Delegates to handle_file_upload with reconstructed event.
        """
        try:
            file_id = event.get('file_id')
            channel = event.get('channel_id')
            user = event.get('user_id')

            if not file_id or not channel:
                return None

            # Fetch file info from Slack
            try:
                file_resp = self.client.files_info(file=file_id)
                if file_resp.get('ok'):
                    file_info = file_resp.get('file', {})
                    synthetic_event = {
                        'channel': channel,
                        'user': user or file_info.get('user'),
                        'files': [file_info],
                        'text': '',
                    }
                    self.handle_file_upload(tenant_id, synthetic_event)
            except SlackApiError as e:
                print(f"[SlackBot] files.info error: {e}", flush=True)

        except Exception as e:
            print(f"[SlackBot] file_shared error: {e}", flush=True)

    def _hyperlink_sources(self, answer: str, sources: list) -> str:
        """
        Replace [Source N] references in the answer text with Slack hyperlinks.
        E.g. [Source 1] → <https://www.use2ndbrain.com/chat|[Knowledge Vault]>
        """
        PORTAL = "https://www.use2ndbrain.com"

        # Build mapping: "1" -> {title, doc_id, source_type, metadata}
        source_map = {}
        for idx, src in enumerate(sources, 1):
            title = self._get_source_title(src)
            doc_id = src.get('doc_id', '')
            metadata = src.get('metadata', {})
            source_type = metadata.get('source_type', '') or src.get('source_type', '')
            external_id = metadata.get('external_id', '') or src.get('external_id', '')
            source_map[str(idx)] = {
                'title': title, 'doc_id': doc_id,
                'source_type': source_type, 'metadata': metadata,
                'external_id': external_id,
            }

        def replace_source(match):
            num = match.group(1)
            info = source_map.get(num)
            if not info:
                return ''
            link = self._get_source_link(
                info['source_type'], info['metadata'],
                info['external_id'], PORTAL, info['doc_id']
            )
            name = info['title'][:45]
            if link:
                return f"<{link}|{name}>"
            return f"*{name}*"

        # Replace [Source 1], [Source 2], etc.
        answer = re.sub(r'\[Source (\d+)\]', replace_source, answer)

        # Handle [Sources 1, 2, 3] or [Source 1, 2] patterns → expand to individual links
        def replace_multi_source(match):
            nums = re.findall(r'\d+', match.group(0))
            parts = []
            for num in nums:
                info = source_map.get(num)
                if not info:
                    continue
                link = self._get_source_link(
                    info['source_type'], info['metadata'],
                    info['external_id'], PORTAL, info['doc_id']
                )
                name = info['title'][:45]
                if link:
                    parts.append(f"<{link}|{name}>")
                else:
                    parts.append(f"*{name}*")
            return ', '.join(parts) if parts else ''

        answer = re.sub(r'\[Sources?\s+[\d,\s]+\]', replace_multi_source, answer)
        return answer

    def _format_search_results(
        self,
        query: str,
        result: Dict,
        compact: bool = False
    ) -> List[Dict]:
        """
        Format search results as Slack blocks with hyperlinked sources.
        Comprehensive answer with inline [Source N] → clickable links.
        """
        PORTAL_URL = "https://www.use2ndbrain.com"
        blocks = []

        answer = result.get('answer', 'No answer available')
        sources = result.get('sources', [])

        # Step 1: Replace [Source N] with hyperlinks BEFORE markdown conversion
        answer = self._hyperlink_sources(answer, sources)

        # Step 2: Convert markdown to Slack mrkdwn (tables→bullets, headers→bold, etc.)
        slack_answer = markdown_to_slack(answer)

        # Step 3: Split into section blocks (max 3000 chars each, up to 3 blocks)
        chunks = self._chunk_text(slack_answer, 3000)
        for chunk in chunks[:3]:
            blocks.append({
                'type': 'section',
                'text': {
                    'type': 'mrkdwn',
                    'text': chunk
                }
            })

        # If answer was truncated, add portal link
        if len(chunks) > 3:
            blocks.append({
                'type': 'section',
                'text': {
                    'type': 'mrkdwn',
                    'text': f"_<{PORTAL_URL}/chat|Read the full answer on the portal...>_"
                }
            })

        # Step 4: Compact hyperlinked sources at bottom
        if sources:
            source_parts = []
            seen_titles = set()

            for source in sources[:8]:
                title = self._get_source_title(source)
                if title in seen_titles:
                    continue
                seen_titles.add(title)

                metadata = source.get('metadata', {})
                source_type = metadata.get('source_type', '') or source.get('source_type', '') or 'document'
                external_id = metadata.get('external_id', '') or source.get('external_id', '')
                doc_id = source.get('doc_id', '')
                type_label = self._get_source_type_label(source_type)
                display_title = title[:50] + "..." if len(title) > 50 else title

                link = self._get_source_link(source_type, metadata, external_id, PORTAL_URL, doc_id)
                if link:
                    source_parts.append(f"<{link}|{display_title}> {type_label}")
                else:
                    source_parts.append(f"{display_title} {type_label}")

                if len(seen_titles) >= 5:
                    break

            if source_parts:
                blocks.append({'type': 'divider'})
                blocks.append({
                    'type': 'context',
                    'elements': [{
                        'type': 'mrkdwn',
                        'text': "*Sources:*  " + "  |  ".join(source_parts)
                    }]
                })

        # Step 5: Feedback buttons
        # Encode query + source doc_ids in the button value for RL tracking
        import json as _json
        source_doc_ids = [s.get('doc_id', '') for s in sources[:10] if s.get('doc_id')]
        feedback_value = _json.dumps({
            'q': query[:200],
            'src': source_doc_ids
        })
        blocks.append({
            'type': 'actions',
            'elements': [
                {
                    'type': 'button',
                    'text': {'type': 'plain_text', 'text': ':thumbsup: Helpful', 'emoji': True},
                    'action_id': 'feedback_helpful',
                    'value': feedback_value
                },
                {
                    'type': 'button',
                    'text': {'type': 'plain_text', 'text': ':thumbsdown: Not Helpful', 'emoji': True},
                    'action_id': 'feedback_not_helpful',
                    'value': feedback_value
                }
            ]
        })

        return blocks

    def _get_source_link(self, source_type: str, metadata: Dict, external_id: str, portal_url: str, doc_id: str = '') -> str:
        """Build a hyperlink URL for a source based on its type.

        Priority: Slack deep link > Gmail deep link > DB source_url > portal fallback
        """
        # Slack messages — deep link to the message
        if source_type == 'slack':
            team_domain = metadata.get('team_domain', '')
            channel_id = metadata.get('channel_id', '')
            message_ts = metadata.get('message_ts', '')
            if team_domain and channel_id and message_ts:
                ts_no_dot = message_ts.replace('.', '')
                return f"https://{team_domain}.slack.com/archives/{channel_id}/p{ts_no_dot}"

        # Gmail — deep link to the email
        if source_type == 'gmail' and external_id:
            return f"https://mail.google.com/mail/u/0/#inbox/{external_id}"

        # Look up document's original source_url from the database
        if doc_id:
            url = self._lookup_source_url(doc_id)
            if url:
                return url

        # Fallback — portal documents page
        return f"{portal_url}/documents"

    def _lookup_source_url(self, doc_id: str) -> Optional[str]:
        """Look up a document's source_url from the database. Uses per-request cache."""
        # Use instance-level cache to avoid repeated DB queries within one message
        if not hasattr(self, '_source_url_cache'):
            self._source_url_cache = {}
        if doc_id in self._source_url_cache:
            return self._source_url_cache[doc_id]

        try:
            from database.models import Document
            db = SessionLocal()
            try:
                doc = db.query(Document.source_url, Document.doc_metadata).filter(
                    Document.id == doc_id
                ).first()
                if doc:
                    url = doc.source_url
                    # Also check doc_metadata for url fields if source_url is empty
                    if not url and doc.doc_metadata:
                        meta = doc.doc_metadata if isinstance(doc.doc_metadata, dict) else {}
                        url = meta.get('url') or meta.get('web_url') or meta.get('webViewLink') or ''
                    self._source_url_cache[doc_id] = url or ''
                    return url or ''
                self._source_url_cache[doc_id] = ''
                return ''
            finally:
                db.close()
        except Exception as e:
            print(f"[SlackBot] Error looking up source_url for {doc_id}: {e}", flush=True)
            self._source_url_cache[doc_id] = ''
            return ''

    def _get_source_title(self, source: Dict) -> str:
        """
        Extract a clean, human-readable title from a source.
        Falls back through multiple strategies to avoid showing raw content.
        """
        metadata = source.get('metadata', {})
        source_type = metadata.get('source_type', '') or source.get('source_type', '')

        # Strategy 1: Direct title field
        title = source.get('title', '') or metadata.get('title', '')

        # Strategy 2: For Slack sources, build from channel + author
        if (not title or title == 'Untitled' or self._looks_like_content(title)) and source_type == 'slack':
            channel_name = metadata.get('channel_name', '')
            author = metadata.get('author', '') or metadata.get('sender', '')
            if channel_name and author:
                title = f"#{channel_name} - {author}"
            elif channel_name:
                title = f"#{channel_name}"
            elif author:
                title = f"Message from {author}"

        # Strategy 3: For Gmail, use subject
        if (not title or title == 'Untitled' or self._looks_like_content(title)) and source_type == 'gmail':
            subject = metadata.get('subject', '')
            sender = metadata.get('sender', '') or metadata.get('author', '')
            if subject:
                title = subject
            elif sender:
                title = f"Email from {sender}"

        # Strategy 4: For other sources, try filename
        if not title or title == 'Untitled' or self._looks_like_content(title):
            filename = metadata.get('filename', '') or metadata.get('file_name', '')
            if filename:
                title = filename

        # Strategy 5: Use content preview as last resort but clean it up
        if not title or title == 'Untitled':
            content = source.get('content', '') or source.get('content_preview', '')
            if content:
                # Take first line/sentence as title
                first_line = content.split('\n')[0].strip()
                first_line = re.sub(r'\s+', ' ', first_line)
                title = first_line[:70] + "..." if len(first_line) > 70 else first_line
            else:
                title = 'Untitled Document'

        # Clean up: remove source type prefixes
        for prefix in ['slack:', 'gmail:', 'box:', 'drive:', 'Slack:', 'Gmail:', 'Box:', 'Drive:']:
            if title.startswith(prefix):
                title = title[len(prefix):].strip()

        return title

    def _looks_like_content(self, title: str) -> bool:
        """Check if a 'title' is actually a content snippet (not a real title)."""
        if not title:
            return True
        # Content snippets are usually long and have many spaces
        if len(title) > 100:
            return True
        # Content usually has lots of words
        if len(title.split()) > 15:
            return True
        return False

    def _get_source_type_label(self, source_type: str) -> str:
        """Get a clean label for the source type."""
        labels = {
            'slack': '(Slack)',
            'gmail': '(Email)',
            'box': '(Box)',
            'google_drive': '(Drive)',
            'google_docs': '(Docs)',
            'google_sheets': '(Sheets)',
            'google_slides': '(Slides)',
            'onedrive': '(OneDrive)',
            'notion': '(Notion)',
            'github': '(GitHub)',
            'outlook': '(Outlook)',
            'zotero': '(Zotero)',
            'email_forward': '(Email)',
            'quartzy': '(Quartzy)',
        }
        return labels.get(source_type, f'({source_type.replace("_", " ").title()})' if source_type else '(Document)')

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
                # Handle single paragraphs that exceed max_length
                if len(paragraph) > max_length:
                    while paragraph:
                        chunks.append(paragraph[:max_length])
                        paragraph = paragraph[max_length:]
                else:
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


# ============================================================================
# SLACK CONNECT: CHANNEL → TENANT MAPPING
# ============================================================================

# Cache for channel → tenant lookups (avoids DB hit per event)
_channel_tenant_cache: Dict[str, Optional[str]] = {}
_channel_cache_lock = threading.Lock()
_channel_cache_ttl: Dict[str, float] = {}
CHANNEL_CACHE_TTL_SECONDS = 600  # 10 min


def get_tenant_for_channel(channel_id: str) -> Optional[str]:
    """
    Look up tenant_id for a Slack Connect shared channel.
    Returns None if channel is not mapped (falls through to workspace lookup).
    """
    if not channel_id:
        return None

    # Check cache
    with _channel_cache_lock:
        if channel_id in _channel_tenant_cache:
            ts = _channel_cache_ttl.get(channel_id, 0)
            if time.time() - ts < CHANNEL_CACHE_TTL_SECONDS:
                cached = _channel_tenant_cache[channel_id]
                if cached:
                    print(f"[SlackBot] Channel cache HIT: {channel_id} -> tenant {cached[:8]}...", flush=True)
                return cached
            else:
                del _channel_tenant_cache[channel_id]
                _channel_cache_ttl.pop(channel_id, None)

    # Query database
    try:
        from database.models import ChannelTenantMapping
        db = SessionLocal()
        try:
            mapping = db.query(ChannelTenantMapping).filter(
                ChannelTenantMapping.channel_id == channel_id,
                ChannelTenantMapping.is_active == True
            ).first()

            tenant_id = mapping.tenant_id if mapping else None

            # Cache result (even None, to avoid repeated DB misses)
            with _channel_cache_lock:
                _channel_tenant_cache[channel_id] = tenant_id
                _channel_cache_ttl[channel_id] = time.time()

            if tenant_id:
                print(f"[SlackBot] Channel mapping found: {channel_id} -> tenant {tenant_id[:8]}...", flush=True)
            return tenant_id
        finally:
            db.close()
    except Exception as e:
        print(f"[SlackBot] Error looking up channel mapping for {channel_id}: {e}", flush=True)
        return None


def invalidate_channel_cache(channel_id: str = None):
    """Invalidate channel tenant cache. If channel_id is None, clear all."""
    with _channel_cache_lock:
        if channel_id:
            _channel_tenant_cache.pop(channel_id, None)
            _channel_cache_ttl.pop(channel_id, None)
        else:
            _channel_tenant_cache.clear()
            _channel_cache_ttl.clear()
