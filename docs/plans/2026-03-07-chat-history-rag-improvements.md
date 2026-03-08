# Chat History + RAG Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Persist chat conversations so users can resume past chats, improve RAG with user context awareness, and clearly attribute sources (user KB vs CTSI vs reproducibility archive).

**Architecture:** The backend already has `ChatConversation` + `ChatMessage` models with full CRUD API (`/api/chat/*`). The frontend `CoWorkChat` currently holds messages in local state only. We wire the frontend to the existing backend API, add a conversation list sidebar, inject user profile context into the RAG system prompt, and tag each source with its origin in the response.

**Tech Stack:** Next.js 14, Flask, SQLAlchemy, Azure OpenAI, Pinecone, SSE streaming

---

## Task 1: Wire CoWorkChat to Persist Conversations

**What:** When a user sends their first message, create a conversation via the backend API. Save each user message and assistant response. When navigating back to /co-work, load the most recent conversation.

**Files:**
- Modify: `frontend/components/co-work/CoWorkChat.tsx`
- Modify: `frontend/app/co-work/page.tsx`

### Step 1: Add conversation state and API helpers to CoWorkChat

In `CoWorkChat.tsx`, add:

```typescript
// Add to props interface
interface CoWorkChatProps {
  apiBase: string
  token: string | null
  onPlanUpdate: (steps: PlanStep[]) => void
  onThinkingStep: (step: ThinkingStep) => void
  onContextUpdate: (ctx: ContextData) => void
  onBriefUpdate: (brief: ResearchBrief) => void
  conversationId?: string | null           // NEW
  onConversationChange?: (id: string) => void  // NEW
}

// Add state inside the component:
const [conversationId, setConversationId] = useState<string | null>(props.conversationId || null)

// API helper functions (inside the component or as module-level functions):

async function createConversation(apiBase: string, token: string, firstMessage: string): Promise<string | null> {
  try {
    const res = await fetch(`${apiBase}/chat/conversations`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: firstMessage.slice(0, 100) })
    })
    const data = await res.json()
    return data.success ? data.conversation.id : null
  } catch { return null }
}

async function saveMessage(apiBase: string, token: string, convId: string, role: string, content: string, sources?: any[]) {
  try {
    await fetch(`${apiBase}/chat/conversations/${convId}/messages`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ role, content, sources })
    })
  } catch (e) { console.error('[Chat] Failed to save message:', e) }
}

async function loadConversation(apiBase: string, token: string, convId: string): Promise<Message[]> {
  try {
    const res = await fetch(`${apiBase}/chat/conversations/${convId}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
    const data = await res.json()
    if (data.success && data.conversation.messages) {
      return data.conversation.messages.map((m: any) => ({
        id: m.id,
        text: m.content,
        isUser: m.role === 'user',
        sources: m.sources || []
      }))
    }
    return []
  } catch { return [] }
}
```

### Step 2: Create conversation on first message, save messages

In the `handleSend()` function (around line 200), after the user message is added to local state, add persistence:

```typescript
// Inside handleSend, after adding user message to state:

let activeConvId = conversationId

// Create conversation on first message
if (!activeConvId && token) {
  activeConvId = await createConversation(apiBase, token, queryText)
  if (activeConvId) {
    setConversationId(activeConvId)
    onConversationChange?.(activeConvId)
  }
}

// Save user message
if (activeConvId && token) {
  saveMessage(apiBase, token, activeConvId, 'user', queryText)
}

// ... (existing streaming logic) ...

// After streaming completes (in the 'done' event handler), save assistant message:
if (activeConvId && token) {
  saveMessage(apiBase, token, activeConvId, 'assistant', fullAnswer, sourcesForResponse)
}
```

### Step 3: Load conversation on mount when conversationId prop is provided

```typescript
// Add useEffect to load conversation when conversationId prop changes
useEffect(() => {
  if (props.conversationId && token) {
    setConversationId(props.conversationId)
    loadConversation(apiBase, token, props.conversationId).then(msgs => {
      if (msgs.length > 0) setMessages(msgs)
    })
  }
}, [props.conversationId, token])
```

### Step 4: Add "New Chat" button

Add a "New Chat" button at the top of the chat panel:

```typescript
// In the chat header area, add:
<button
  onClick={() => {
    setMessages([])
    setConversationId(null)
    onConversationChange?.('')
    onPlanUpdate([])
    onContextUpdate({ documents: [], pubmed_papers: [], journals: [], experiments: [] })
    onBriefUpdate({ heading: '', description: '', keyPoints: [] })
  }}
  style={{
    padding: '6px 14px',
    borderRadius: '8px',
    border: `1px solid ${COLORS.border}`,
    backgroundColor: COLORS.cardBg,
    color: COLORS.textSecondary,
    fontSize: '13px',
    cursor: 'pointer',
    fontFamily: FONT,
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
  }}
>
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
  </svg>
  New Chat
</button>
```

### Step 5: Commit

```bash
git add frontend/components/co-work/CoWorkChat.tsx frontend/app/co-work/page.tsx
git commit -m "feat: persist chat conversations to backend API"
```

---

## Task 2: Add Conversation History Sidebar

**What:** Add a collapsible conversation list on the left side of the chat panel so users can switch between past conversations. Fetch recent conversations from `GET /api/chat/conversations`.

**Files:**
- Create: `frontend/components/co-work/CoWorkHistory.tsx`
- Modify: `frontend/app/co-work/page.tsx`

### Step 1: Create CoWorkHistory component

```typescript
// frontend/components/co-work/CoWorkHistory.tsx
'use client'

import React, { useState, useEffect } from 'react'

const COLORS = {
  primary: '#C9A598',
  primaryLight: '#FBF4F1',
  pageBg: '#FAF9F7',
  cardBg: '#FFFFFF',
  textPrimary: '#2D2D2D',
  textSecondary: '#6B6B6B',
  textMuted: '#9A9A9A',
  border: '#F0EEEC',
}
const FONT = "Avenir, 'Avenir Next', 'DM Sans', system-ui, sans-serif"

interface Conversation {
  id: string
  title: string
  last_message_at: string
  message_count: number
}

interface CoWorkHistoryProps {
  apiBase: string
  token: string | null
  activeConversationId: string | null
  onSelectConversation: (id: string) => void
  onNewChat: () => void
}

export default function CoWorkHistory({
  apiBase, token, activeConversationId, onSelectConversation, onNewChat
}: CoWorkHistoryProps) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [isOpen, setIsOpen] = useState(true)

  useEffect(() => {
    if (!token) return
    fetchConversations()
  }, [token])

  const fetchConversations = async () => {
    try {
      const res = await fetch(`${apiBase}/chat/conversations?limit=20`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      const data = await res.json()
      if (data.success) {
        setConversations(data.conversations || [])
      }
    } catch (e) {
      console.error('[History] Failed to fetch conversations:', e)
    }
  }

  // Refresh when a new conversation is created
  useEffect(() => {
    if (activeConversationId) fetchConversations()
  }, [activeConversationId])

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    if (diff < 86400000) return 'Today'
    if (diff < 172800000) return 'Yesterday'
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  // Render as a thin sidebar strip
  return (
    <div style={{
      width: isOpen ? '220px' : '44px',
      height: '100%',
      borderRight: `1px solid ${COLORS.border}`,
      backgroundColor: COLORS.pageBg,
      transition: 'width 0.2s ease',
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
      flexShrink: 0,
    }}>
      {/* Toggle + New Chat header */}
      <div style={{
        padding: '12px 10px',
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        borderBottom: `1px solid ${COLORS.border}`,
      }}>
        <button onClick={() => setIsOpen(!isOpen)} style={{
          width: '28px', height: '28px', borderRadius: '6px',
          border: 'none', backgroundColor: 'transparent', cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: COLORS.textSecondary, flexShrink: 0,
        }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>
        {isOpen && (
          <span style={{
            fontSize: '13px', fontWeight: 600, color: COLORS.textPrimary,
            fontFamily: FONT, flex: 1,
          }}>
            Chats
          </span>
        )}
      </div>

      {/* Conversation list (only when open) */}
      {isOpen && (
        <div style={{ flex: 1, overflowY: 'auto', padding: '8px 6px' }}>
          {conversations.length === 0 ? (
            <p style={{
              fontSize: '12px', color: COLORS.textMuted,
              textAlign: 'center', padding: '20px 8px',
              fontFamily: FONT,
            }}>
              No conversations yet
            </p>
          ) : (
            conversations.map(conv => (
              <button
                key={conv.id}
                onClick={() => onSelectConversation(conv.id)}
                style={{
                  width: '100%',
                  padding: '10px 10px',
                  borderRadius: '8px',
                  border: 'none',
                  backgroundColor: conv.id === activeConversationId ? COLORS.primaryLight : 'transparent',
                  cursor: 'pointer',
                  textAlign: 'left',
                  marginBottom: '2px',
                  transition: 'background-color 0.15s',
                }}
              >
                <div style={{
                  fontSize: '13px', fontWeight: 500,
                  color: COLORS.textPrimary, fontFamily: FONT,
                  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                }}>
                  {conv.title || 'Untitled'}
                </div>
                <div style={{
                  fontSize: '11px', color: COLORS.textMuted,
                  fontFamily: FONT, marginTop: '2px',
                }}>
                  {formatDate(conv.last_message_at)}
                </div>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  )
}
```

### Step 2: Integrate history sidebar into co-work page

In `frontend/app/co-work/page.tsx`, add conversation state management and pass it through:

```typescript
// Add imports:
import CoWorkHistory from '@/components/co-work/CoWorkHistory'

// Add state to CoWorkPage:
const [activeConversationId, setActiveConversationId] = useState<string | null>(null)

// In the layout, wrap the chat panel with the history sidebar:
{/* Left: History + Chat panel (~40%) */}
<div style={{
  width: '40%',
  minWidth: '340px',
  height: '100%',
  overflow: 'hidden',
  display: 'flex',          // NEW: flex row for history + chat
}}>
  <CoWorkHistory
    apiBase={API_BASE}
    token={token}
    activeConversationId={activeConversationId}
    onSelectConversation={(id) => setActiveConversationId(id)}
    onNewChat={() => setActiveConversationId(null)}
  />
  <div style={{ flex: 1, height: '100%', overflow: 'hidden' }}>
    <CoWorkChat
      apiBase={API_BASE}
      token={token}
      conversationId={activeConversationId}
      onConversationChange={(id) => setActiveConversationId(id || null)}
      onPlanUpdate={handlePlanUpdate}
      onThinkingStep={handleThinkingStep}
      onContextUpdate={handleContextUpdate}
      onBriefUpdate={handleBriefUpdate}
    />
  </div>
</div>
```

### Step 3: Auto-load last conversation on mount

In `CoWorkPage`, add a useEffect that fetches the most recent conversation on mount:

```typescript
useEffect(() => {
  if (!token) return
  // Load most recent conversation
  fetch(`${API_BASE}/chat/conversations?limit=1`, {
    headers: { 'Authorization': `Bearer ${token}` }
  })
    .then(r => r.json())
    .then(data => {
      if (data.success && data.conversations?.length > 0) {
        setActiveConversationId(data.conversations[0].id)
      }
    })
    .catch(() => {})
}, [token])
```

### Step 4: Commit

```bash
git add frontend/components/co-work/CoWorkHistory.tsx frontend/app/co-work/page.tsx
git commit -m "feat: add conversation history sidebar with auto-resume"
```

---

## Task 3: Inject User Context into RAG System Prompt

**What:** Include user's name, organization, and a summary of their data inventory in the RAG system prompt so the AI knows who it's talking to and what data it has access to.

**Files:**
- Modify: `backend/services/enhanced_search_service.py:1593-1688` (`_get_mode_config`)
- Modify: `backend/services/enhanced_search_service.py:1689-1820` (`generate_answer`)
- Modify: `backend/services/enhanced_search_service.py` (streaming equivalent)
- Modify: `backend/app_v2.py:1596-1782` (search/stream endpoint)

### Step 1: Add user_context parameter to `_get_mode_config`

In `enhanced_search_service.py`, modify `_get_mode_config` to accept and inject user context:

```python
def _get_mode_config(self, response_mode: int, query: str, context: str, user_context: dict = None):
    # ... existing code for modes 1 and 2 ...

    else:  # Mode 3 (default)
        # Build user context section
        user_context_section = ""
        if user_context:
            parts = []
            if user_context.get('user_name'):
                parts.append(f"- The user's name is {user_context['user_name']}")
            if user_context.get('organization'):
                parts.append(f"- They belong to organization: {user_context['organization']}")
            if user_context.get('data_summary'):
                parts.append(f"- Their knowledge base contains: {user_context['data_summary']}")
            if parts:
                user_context_section = "\n\nUSER CONTEXT:\n" + "\n".join(parts) + "\n"

        system_prompt = f"""You are a precise knowledge assistant. You ONLY answer based on the provided source documents.
{user_context_section}
... (rest of existing system prompt) ...

SOURCE ATTRIBUTION (ALWAYS indicate where information comes from):
- Prefix with **[Your KB]** for documents from the user's uploaded files, emails, Slack messages, or integrated services
- Prefix with **[CTSI Research]** for CTSI shared research core data
- Prefix with **[Repro Archive]** for failed/negative experiment data from the reproducibility archive
- Prefix with **[PubMed]** for academic papers
- Prefix with **[Journal DB]** for journal database entries
If a source is from the user's knowledge base, say so explicitly (e.g., "From your uploaded documents...").
If a source is from shared CTSI data, say "From the CTSI research database...".
"""
```

### Step 2: Build user_context dict in the search/stream endpoint

In `app_v2.py`, in both `/api/search` and `/api/search/stream`, build a user_context dict from the authenticated user:

```python
# Inside the generate() function of /api/search/stream, after getting tenant:
from database.models import User, Document
from sqlalchemy import func

# Build user context
user_context = {}
try:
    user = db.query(User).filter(User.id == g.user_id).first()
    if user:
        user_context['user_name'] = user.full_name
    if tenant:
        user_context['organization'] = tenant.name

    # Build data inventory summary
    doc_counts = db.query(
        Document.source_type,
        func.count(Document.id)
    ).filter(
        Document.tenant_id == tenant_id
    ).group_by(Document.source_type).all()

    if doc_counts:
        summary_parts = []
        for source_type, count in doc_counts:
            label = {
                'email': 'emails',
                'message': 'Slack messages',
                'file': 'uploaded files',
                'document': 'documents',
                'grant': 'grant documents',
            }.get(source_type, f'{source_type} items')
            summary_parts.append(f"{count} {label}")
        user_context['data_summary'] = ", ".join(summary_parts)
except Exception as e:
    print(f"[SEARCH-STREAM] Error building user context: {e}", flush=True)
```

Then pass `user_context` to `enhanced_service.search_and_answer_stream()` and down to `generate_answer()` / `_get_mode_config()`.

### Step 3: Pass user_context through the search service methods

In `enhanced_search_service.py`, add `user_context` parameter to:
- `search_and_answer()`
- `search_and_answer_stream()`
- `generate_answer()`
- `generate_answer_stream()`

And pass it to `_get_mode_config()`:

```python
def generate_answer(self, query, search_results, validate=True, max_context_tokens=12000,
                    conversation_history=None, response_mode=3, user_context=None):
    # ...
    system_prompt, user_instruction, temperature, max_tokens, freq_penalty = \
        self._get_mode_config(response_mode, query, context, user_context=user_context)
```

### Step 4: Commit

```bash
git add backend/services/enhanced_search_service.py backend/app_v2.py
git commit -m "feat: inject user context (name, org, data inventory) into RAG prompt"
```

---

## Task 4: Tag Sources with Origin Type in Search Results

**What:** Each source returned by the RAG should carry a `source_origin` field indicating whether it came from the user's KB, CTSI shared data, reproducibility archive, PubMed, or journal DB. The frontend should display this as a badge.

**Files:**
- Modify: `backend/app_v2.py:1690-1728` (search_complete handler in stream endpoint)
- Modify: `backend/services/enhanced_search_service.py` (search result enrichment)
- Modify: `frontend/components/co-work/CoWorkChat.tsx` (source badge rendering)

### Step 1: Add source_origin to each source in the stream endpoint

In `app_v2.py`, in the `search_complete` event handler within `/api/search/stream`, determine origin:

```python
# After building source_entry, determine origin:
if is_shared:
    source_entry["source_origin"] = "ctsi"
    source_entry["source_origin_label"] = "CTSI Research"
else:
    # Look up document source_type from DB
    doc_source_type = None
    if doc_id:
        try:
            doc = db.query(Document.source_type).filter(Document.id == doc_id).first()
            if doc:
                doc_source_type = doc.source_type
        except Exception:
            pass

    if doc_source_type == 'pubmed':
        source_entry["source_origin"] = "pubmed"
        source_entry["source_origin_label"] = "PubMed"
    elif doc_source_type == 'journal':
        source_entry["source_origin"] = "journal"
        source_entry["source_origin_label"] = "Journal DB"
    elif doc_source_type == 'experiment':
        source_entry["source_origin"] = "reproducibility"
        source_entry["source_origin_label"] = "Repro Archive"
    else:
        source_entry["source_origin"] = "user_kb"
        source_entry["source_origin_label"] = "Your KB"
```

### Step 2: Show source origin badges in the frontend

In `CoWorkChat.tsx`, where sources are rendered (the source badges at the bottom of messages), add an origin label:

```typescript
// In the source badge rendering section:
const originColors: Record<string, string> = {
  user_kb: '#9CB896',      // green
  ctsi: '#7BA7C9',          // blue
  pubmed: '#C9A598',        // warm
  journal: '#B39DDB',       // purple
  reproducibility: '#FFB74D', // orange
}

// Add to each source badge:
{source.source_origin_label && (
  <span style={{
    fontSize: '10px',
    padding: '2px 6px',
    borderRadius: '4px',
    backgroundColor: originColors[source.source_origin] || '#E0E0E0',
    color: '#FFFFFF',
    fontWeight: 600,
    marginLeft: '6px',
  }}>
    {source.source_origin_label}
  </span>
)}
```

### Step 3: Commit

```bash
git add backend/app_v2.py frontend/components/co-work/CoWorkChat.tsx
git commit -m "feat: tag and display source origin (KB/CTSI/PubMed/Repro Archive)"
```

---

## Task 5: Add Source Context to RAG Source Documents

**What:** When building the context for the LLM, prepend each source's origin so the LLM knows which pool it came from and can attribute correctly.

**Files:**
- Modify: `backend/services/enhanced_search_service.py:1723-1760` (`generate_answer` context building)

### Step 1: Add source origin tag to context_parts

In `generate_answer()`, when building `context_parts`, add the origin label:

```python
# Determine origin label for each source
origin_tag = ""
if result.get('is_shared'):
    origin_tag = "[CTSI Research]"
elif result.get('source_type') == 'pubmed':
    origin_tag = "[PubMed]"
elif result.get('source_type') == 'journal':
    origin_tag = "[Journal DB]"
elif result.get('source_type') == 'experiment':
    origin_tag = "[Repro Archive]"
else:
    origin_tag = "[Your KB]"

context_parts.append(
    f"[Source {source_idx}] {origin_tag} (Relevance: {score:.2%})\n"
    f"Title: {title}\n"
    f"Content: {content}\n"
)
```

### Step 2: Do the same in `generate_answer_stream()`

Apply identical logic to the streaming version of `generate_answer`.

### Step 3: Commit

```bash
git add backend/services/enhanced_search_service.py
git commit -m "feat: add source origin tags to RAG context for attribution"
```

---

## Task 6: Improve Query Understanding with User Data Awareness

**What:** When a user says "my CSV files" or "the data I uploaded yesterday", the RAG should understand what they mean. Add a query preprocessor that resolves user references by checking recent uploads and user metadata.

**Files:**
- Modify: `backend/services/enhanced_search_service.py` (add `_resolve_user_references` method)
- Modify: `backend/app_v2.py` (pass recent_uploads context to search)

### Step 1: Add reference resolver to enhanced search service

```python
def _resolve_user_references(self, query: str, user_context: dict = None) -> str:
    """
    Expand vague user references into searchable terms.
    E.g., 'my CSV files' -> 'CSV files uploaded by <user_name>'
    E.g., 'the experiment data' -> search recent uploads for experiment-related docs
    """
    if not user_context:
        return query

    expanded = query
    user_name = user_context.get('user_name', '')
    recent_docs = user_context.get('recent_doc_titles', [])

    # Resolve possessive references
    possessive_patterns = [
        (r'\bmy (?:files?|documents?|data|uploads?)\b', f'{user_name}\'s uploaded documents'),
        (r'\bour (?:lab|team|group)\b', user_context.get('organization', 'organization')),
    ]

    for pattern, replacement in possessive_patterns:
        import re
        if re.search(pattern, expanded, re.IGNORECASE):
            expanded = re.sub(pattern, replacement, expanded, flags=re.IGNORECASE)

    # If query mentions "recent" or "latest", boost recent doc context
    if re.search(r'\b(recent|latest|last|yesterday|today)\b', expanded, re.IGNORECASE) and recent_docs:
        doc_context = ", ".join(recent_docs[:5])
        expanded += f" (recent documents: {doc_context})"

    if expanded != query:
        print(f"[EnhancedSearch] Resolved references: '{query}' -> '{expanded}'")

    return expanded
```

### Step 2: Fetch recent document titles in the stream endpoint

In `app_v2.py`, add recent doc titles to user_context:

```python
# After building user_context, add recent docs:
try:
    recent_docs = db.query(Document.title).filter(
        Document.tenant_id == tenant_id
    ).order_by(Document.created_at.desc()).limit(10).all()
    user_context['recent_doc_titles'] = [d.title for d in recent_docs if d.title]
except Exception:
    pass
```

### Step 3: Call resolver before search

In the search flow, call `_resolve_user_references(query, user_context)` before expanding the query with the existing `QueryExpander`.

### Step 4: Commit

```bash
git add backend/services/enhanced_search_service.py backend/app_v2.py
git commit -m "feat: resolve user references (my files, our lab) in queries"
```

---

## Task 7: Build and Deploy

**What:** Build Docker images for both frontend and backend, push to ECR, deploy to ECS.

### Step 1: Build frontend

```bash
docker build --platform linux/amd64 --no-cache -t secondbrain-frontend:latest -f frontend/Dockerfile frontend/
```

### Step 2: Build backend

```bash
docker build --platform linux/amd64 --no-cache -t secondbrain-backend:latest -f backend/Dockerfile backend/
```

### Step 3: Push to ECR

```bash
aws ecr get-login-password --region us-east-2 | docker login --username AWS --password-stdin 923028187100.dkr.ecr.us-east-2.amazonaws.com

docker tag secondbrain-frontend:latest 923028187100.dkr.ecr.us-east-2.amazonaws.com/secondbrain-frontend:latest
docker push 923028187100.dkr.ecr.us-east-2.amazonaws.com/secondbrain-frontend:latest

docker tag secondbrain-backend:latest 923028187100.dkr.ecr.us-east-2.amazonaws.com/secondbrain-backend:latest
docker push 923028187100.dkr.ecr.us-east-2.amazonaws.com/secondbrain-backend:latest
```

### Step 4: Deploy to ECS

```bash
aws ecs update-service --cluster secondbrain-cluster --service secondbrain-frontend --force-new-deployment --region us-east-2
aws ecs update-service --cluster secondbrain-cluster --service secondbrain-backend --force-new-deployment --region us-east-2
```

### Step 5: Verify

```bash
# Wait 2-3 minutes, then check
aws ecs describe-services --cluster secondbrain-cluster --services secondbrain-frontend secondbrain-backend --region us-east-2 --query 'services[*].{name:serviceName,running:runningCount,desired:desiredCount}'
```

---

## Summary

| Task | What | Impact |
|------|------|--------|
| 1 | Persist conversations to backend | Chat survives page navigation |
| 2 | Conversation history sidebar | Switch between past chats |
| 3 | User context in RAG prompt | AI knows who you are and what data you have |
| 4 | Source origin badges | Clear visual: KB vs CTSI vs Repro Archive |
| 5 | Source tags in RAG context | LLM accurately attributes information |
| 6 | User reference resolution | "my CSV files" actually works |
| 7 | Build & deploy | Ship to production |
