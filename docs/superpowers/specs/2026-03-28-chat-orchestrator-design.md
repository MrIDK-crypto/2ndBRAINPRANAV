# Chat Orchestrator — Integrating Powers into Co-Work

**Date**: 2026-03-28
**Status**: Approved (v2 — post-review fixes)
**Author**: Pranav + Claude

## Problem

HIJ, Competitor Finder, Idea Reality, and Co-Researcher exist as standalone pages/services. They need to be accessible through the Co-Work chatbot with full lab context preloaded, while standalone versions remain untouched.

## Design Decisions

- **Dual versions**: Integrated (chatbot, context-aware, login required) + Standalone (existing pages, no login)
- **Intent detection**: Hybrid — auto-detect from natural language + explicit trigger button
- **Context**: Full RAG pipeline (all user docs) + cached research profile
- **Multi-service**: Parallel fan-out when multiple services are relevant
- **Response format**: Tabbed card with summary per service + "View full analysis" link
- **Existing service code**: Never modified — new adapters wrap existing services
- **Auth**: Orchestrated endpoint always requires login. Standalone pages handle their own auth independently.

## Architecture

```
User message in Co-Work
        |
   LAYER 1: Intent Gate (keyword + embedding similarity)
        |
   no powers needed? --> Standard RAG chat (existing /api/search/stream flow)
        |
   powers needed
        |
   Context Injector (RAG chunks + cached research profile)
        |
   LAYER 2: LLM Tool-Use Router (GPT function-calling)
        |  Returns: [{tool, args}, ...]
        |  SKIPPED when power_hint is set + single intent (just extract params)
        |
   LAYER 3: Parallel Executor (ThreadPoolExecutor, concurrent service calls)
        |  Returns: [{service, status, summary, full_results}, ...]
        |
   Response Merger (final LLM call -> tabbed summary)
        |
   Tabbed card in chat UI (persisted as ChatMessage with type=power_result)
```

### Relationship with Existing IntentClassifier

The codebase has an existing `backend/services/intent_classifier.py` used by `/api/search/stream`. The new Intent Gate runs FIRST. If no powers are detected, the request flows to the existing `/api/search/stream` endpoint with its own IntentClassifier — that flow is completely unchanged. The Intent Gate only intercepts messages that need power services.

## Layer 1: Intent Gate

Fast triage — should this message use powers or go to standard chat?

**Two-stage check:**
1. Keyword/regex scan (<1ms) — pattern match against known trigger phrases
2. Embedding similarity fallback (~200ms) — cosine similarity against 4 pre-computed power description embeddings, threshold configurable via `POWER_INTENT_THRESHOLD` env var (default 0.75)

**Explicit trigger bypass:** When user clicks a power from the UI trigger button, frontend attaches `power_hint: "hij"` to the request, skipping Layer 1 entirely. When `power_hint` is set for a single service, Layer 2 is also skipped — we just extract parameters and go straight to execution.

**Keyword patterns:**

| Power | Triggers |
|-------|----------|
| HIJ | score, manuscript, journal match, impact factor, red flags, review my paper, publish, where should I submit |
| Competitor Finder | competitor, competing lab, who else, grants in my area, preprints, similar research |
| Idea Reality | validate idea, is this novel, does this exist, reality check, feasibility, has anyone done |
| Co-Researcher | hypothesis, brainstorm research, agent debate, co-research, research directions |

## File Upload Pipeline

Services like HIJ and Co-Researcher need file attachments. The orchestrated endpoint accepts multipart form data.

**Flow:**
```
1. User clicks power trigger -> selects "Score Manuscript"
2. File picker opens -> user selects paper.pdf
3. Frontend sends multipart POST to /api/chat/orchestrated:
   - field "message": user's text message
   - field "metadata": JSON string with power_hint, conversation_id
   - field "files": one or more file uploads
4. Backend stores files temporarily in /tmp/orchestrator/{request_id}/
5. Adapters receive file paths, read bytes as needed
6. Temp files cleaned up after response completes
```

**No-file fallback for HIJ:** If HIJ is triggered via auto-detect (no explicit trigger) and no file is attached:
- If the user's message contains substantial text (>200 words), use it as `raw_text` input
- Otherwise, return an SSE event `event: file_needed` prompting the user to attach a paper

## Context Injector

Pulls user's lab context before Layer 2 runs. Always requires authentication.

**Components:**
1. **RAG Query** — existing Pinecone pipeline, query = user message, namespace = tenant_id, top 15 chunks reranked
2. **Research Profile** — cached JSON per tenant, lazy-built and stored in database

**Research Profile schema:**
```json
{
  "primary_fields": ["molecular biology", "CRISPR"],
  "recent_topics": ["delivery mechanisms", "base editing"],
  "institution": "MIT",
  "collaborators": ["Dr. Smith", "Dr. Chen"],
  "recent_papers": ["Paper A title", "Paper B title"],
  "methodology_preferences": ["in vivo", "mouse models"],
  "updated_at": "2026-03-28T00:00:00Z"
}
```

### Research Profile Builder

**How it's built:** One LLM call over the user's 20 most recent documents' `structured_summary` JSON fields (already extracted by `extraction_service.py` during sync). Extracts fields, topics, collaborators, institution, methodology patterns.

**Storage:** New `research_profile` JSON column on the `Tenant` model + `profile_updated_at` timestamp column.

**Refresh strategy:** Lazy rebuild. On each orchestrated request, check if `profile_updated_at` is older than 24 hours or null. If stale, rebuild inline (adds ~3s on first query, then cached). Use a `profile_building` boolean flag on the Tenant to prevent concurrent rebuilds — if flag is set, use stale profile rather than waiting.

**Cold start:** If no profile exists and no documents are synced, `research_profile = null`. Services receive no context and behave like standalone versions.

**Context flow per service:**

| Service | Context used |
|---------|-------------|
| HIJ | Research profile (field hint, related papers), relevant chunks (prior work) |
| Competitor Finder | Research profile (institution, fields, topics as search seeds) |
| Idea Reality | Research profile (existing work to avoid self-flagging) |
| Co-Researcher | Relevant chunks (domain knowledge), research profile (methodology prefs) |

## Layer 2: LLM Tool-Use Router

One GPT call with function-calling definitions:

```
Tools available:
- score_manuscript(paper_text, focus_areas?, skip_steps?)
- find_competitors(topics, field, institution_filter?)
- validate_idea(idea_description, domain?)
- run_co_researcher(protocol_text?, paper_text?, research_question?)
```

System prompt instructs the LLM to:
- Analyze the user's message and research context
- Decide which tool(s) to call
- Extract parameters from the message
- Return structured tool_calls array

The LLM can call multiple tools in one response for multi-intent messages.

**Optimization:** When `power_hint` is set and only one service is implied, skip Layer 2 entirely. Use a lightweight parameter extraction (regex + simple LLM call with minimal prompt) instead of the full tool-use router. This saves ~2s and one expensive LLM call on explicit triggers.

## Layer 3: Parallel Executor

Takes tool_calls array, fires all concurrently using `concurrent.futures.ThreadPoolExecutor`.

**Thread safety:** Each thread creates its own SQLAlchemy database session via `get_db_session()`. Sessions are closed in the thread's finally block.

### Adapter Pattern

Each service has an adapter that:
1. Translates orchestrator args -> service-specific format
2. Injects context_package fields relevant to that service
3. Calls the existing service function
4. Returns standardized envelope

### Adapter Implementation Notes

**HIJ and Competitor Finder adapters** — these services return SSE generator strings (`"event: progress\ndata: {...}\n\n"`). The adapters must consume the full generator and parse SSE strings back into structured data. Helper utility: `parse_sse_stream(generator) -> List[dict]` in `adapters/__init__.py`.

**Co-Researcher adapter** — this service is stateful (sessions, messages). For the orchestrated integration:
- Create a one-shot ephemeral session (not persisted to the research sessions table)
- Call the underlying reasoning methods directly rather than `process_message_stream`
- Return structured insights without creating persistent state
- If the user wants to continue the research thread, they can use the standalone Co-Researcher page

**Idea Reality adapter** — simplest, returns plain dict. Minimal transformation needed.

**Result envelope:**
```json
{
  "service": "hij",
  "status": "success",
  "summary": "LLM-generated 2-3 sentence summary",
  "full_results": { ... },
  "error": null
}
```

Error envelope (for partial failures):
```json
{
  "service": "competitor_finder",
  "status": "timeout",
  "summary": null,
  "full_results": null,
  "error": "Service timed out after 90s. Try the standalone Competitor Finder for full results."
}
```

**Timeouts:** 90s per service (wall-clock), 120s total wall-clock for the entire ThreadPoolExecutor. Partial results returned if some services fail — successful results are merged, failed services show error tabs.

## Response Merger

Final LLM call takes all result envelopes + research profile and generates:

```json
{
  "type": "power_result",
  "tabs": [
    {
      "label": "Manuscript Score",
      "icon": "file-text",
      "status": "success",
      "summary": "Personalized markdown summary...",
      "full_results": { ... }
    },
    {
      "label": "Competitors",
      "icon": "search",
      "status": "timeout",
      "summary": "Search timed out. Try again or use the standalone page.",
      "full_results": null
    }
  ],
  "followup_suggestions": [
    "Want me to generate code from this paper?",
    "Should I check idea novelty?"
  ]
}
```

The summary is personalized: "Based on your recent CRISPR delivery work, your manuscript scores 7.8/10..." rather than generic output.

**Error tab handling:** Failed services still get a tab, but with `status: "timeout"|"error"` and a user-friendly error message as the summary. The user sees all tabs but can tell which succeeded.

## Conversation Persistence

Orchestrated results are stored as regular `ChatMessage` entries in the existing conversation system.

**Message type field:** Add `message_type` column to the chat message model (or use `extra_data.type`):
- `"text"` — regular chat message (default, backward-compatible)
- `"power_result"` — orchestrated power result

**Serialization:** The full merger response JSON (tabs, followup_suggestions) is stored in the message's `extra_data` field. On conversation reload, the frontend checks `message_type` — if `"power_result"`, render `PowerResultCard` instead of a plain markdown bubble.

**Full analysis retrieval:** No separate endpoint needed. The `full_results` object is stored inline in `extra_data.tabs[n].full_results`. When the user clicks "View full analysis," the frontend reads from the already-loaded message data. This avoids a separate storage/retrieval system.

## SSE Event Contract

The orchestrated endpoint emits its own event types, distinct from the existing `/api/search/stream` events. The frontend conditionally uses the orchestrated endpoint based on whether powers are detected.

**Routing logic in CoWorkChat.tsx:**
```
if (power_hint || intent_gate_detected_powers):
    POST /api/chat/orchestrated   -> handle orchestrator SSE events
else:
    POST /api/search/stream       -> handle existing search SSE events (unchanged)
```

**Orchestrator SSE events:**

```
event: thinking
data: {"step": "Analyzing your request..."}

event: file_needed
data: {"service": "hij", "message": "Please attach your manuscript to score it."}

event: context_loaded
data: {"profile_fields": ["CRISPR", "gene therapy"], "chunks_found": 12}

event: services_started
data: {"services": ["hij", "competitor_finder"]}

event: service_progress
data: {"service": "hij", "step": "Analyzing methodology...", "percent": 45}

event: service_complete
data: {"service": "hij", "status": "success"}

event: service_complete
data: {"service": "competitor_finder", "status": "success"}

event: result
data: {"type": "power_result", "tabs": [...], "followup_suggestions": [...]}

event: done
data: {}
```

**Existing search/stream events are completely unchanged.** The frontend uses two separate SSE handlers — the existing one for standard chat and a new one for orchestrated powers.

## Frontend Changes

### 1. Powers Trigger Button

Location: Next to the send arrow in the chat input bar.

A button (lightning bolt icon) that opens a popover menu:
- Score Manuscript (triggers file picker)
- Find Competitors
- Validate Idea
- Co-Researcher (triggers file picker)

Clicking attaches `power_hint` to the next message. Services that need a file (HIJ, Co-Researcher) also open the file picker. The selected file is held in component state until the user sends their message.

### 2. Tabbed Result Card

New chat bubble component: `PowerResultCard`
- Renders tabs from the merger response
- Each tab shows markdown summary
- Error tabs show warning styling + error message
- "View full analysis" button per tab opens detailed results in the right panel

### 3. Loading State Card

New component: `PowerLoadingCard`
- Animated card showing which services are running
- Checkmarks appear as each service completes
- Progress text updates from `service_progress` SSE events

### 4. Full Analysis Panel

The existing right panel (context/plan area) gains a new mode: full analysis view. When user clicks "View full analysis," the panel renders the `full_results` JSON for that service. Uses the same rendering logic as the standalone pages but embedded in the panel.

### 5. CoWorkChat.tsx Modifications

This file WILL be modified to:
- Add the PowersTrigger button to the input bar
- Add routing logic to choose between `/api/search/stream` and `/api/chat/orchestrated`
- Add a new SSE handler for orchestrator events
- Render `PowerResultCard` when `message_type === "power_result"` in conversation history
- Render `PowerLoadingCard` during orchestrated requests

## New Backend Files

```
backend/services/chat_orchestrator/
  __init__.py
  intent_gate.py          # Layer 1: keyword + embedding gate
  context_injector.py     # RAG + research profile
  tool_router.py          # Layer 2: LLM tool-use call
  parallel_executor.py    # Layer 3: ThreadPoolExecutor + timeout mgmt
  response_merger.py      # Summary generation
  adapters/
    __init__.py            # Shared: parse_sse_stream() utility
    hij_adapter.py         # Wraps journal_scorer_service
    competitor_adapter.py  # Wraps competitor_finder_service
    idea_adapter.py        # Wraps idea_reality_service
    co_researcher_adapter.py # Wraps co_researcher_service (one-shot, no session)

backend/services/research_profile_service.py  # Lazy-built cached profile

backend/api/orchestrator_routes.py  # New blueprint: /api/chat/orchestrated
```

## New Frontend Files

```
frontend/components/co-work/
  PowersTrigger.tsx        # Button + popover menu next to send arrow
  PowerResultCard.tsx      # Tabbed result card chat bubble
  PowerLoadingCard.tsx     # Animated loading state with service progress
  FullAnalysisPanel.tsx    # Right panel full results view
```

## Modified Files

**Backend:**
- `backend/database/models.py` — add `research_profile` JSON + `profile_updated_at` to Tenant model, add `message_type` to chat message model
- `backend/app_v2.py` — register new orchestrator_routes blueprint

**Frontend:**
- `frontend/components/co-work/CoWorkChat.tsx` — add powers trigger, SSE handler routing, power result rendering

## Files NOT Modified (Standalone Preserved)

- `backend/services/journal_scorer_service.py`
- `backend/services/competitor_finder_service.py`
- `backend/services/idea_reality_service.py`
- `backend/services/co_researcher_service.py`
- `backend/api/journal_routes.py`
- `backend/api/competitor_finder_routes.py`
- `backend/api/idea_reality_routes.py`
- `backend/api/co_researcher_routes.py`
- `frontend/app/high-impact-journal/page.tsx`
- `frontend/app/co-researcher/page.tsx`
- `frontend/components/high-impact-journal/HighImpactJournal.tsx`
- `frontend/components/co-researcher/CoResearcher.tsx`

## API Contract

### POST /api/chat/orchestrated

**Auth:** `@require_auth` — always requires login.

**Request:** Multipart form data
- `message` (string): User's text message
- `metadata` (JSON string): `{"conversation_id": "uuid", "power_hint": "hij|competitors|idea|co_researcher|null"}`
- `files` (file[]): Optional file attachments

**Response:** SSE stream (see SSE Event Contract above)

## Cost Considerations

A single orchestrated query can trigger multiple LLM calls:

| Call | When | Est. Cost |
|------|------|-----------|
| Layer 1 embedding | Only if keyword match fails | ~$0.001 |
| Layer 2 tool-use router | Only for auto-detect multi-intent (skipped for power_hint) | ~$0.01 |
| Response merger | Always | ~$0.01 |
| Service-internal LLM calls | Per service (HIJ: ~5 calls, Competitors: ~1, Idea: ~0, Co-Researcher: ~3) | ~$0.05-0.15 |

**Total range:** $0.02 (single explicit trigger) to $0.20 (multi-service auto-detect with HIJ)

**Optimizations applied:**
- Layer 1 keyword match avoids embedding call for ~70% of messages
- Explicit triggers skip both Layer 1 and Layer 2
- Research profile cached (not rebuilt per query)

## Testing Strategy

1. **Unit tests** for intent gate (keyword matching, embedding threshold, power_hint bypass)
2. **Unit tests** for each adapter (input/output transformation, SSE parsing)
3. **Unit tests** for research profile builder (cold start, stale refresh, concurrent build guard)
4. **Integration test** for full pipeline (message -> tabbed result)
5. **Integration test** for partial failure (one service times out, others succeed)
6. **Manual test** for standalone pages (verify nothing broken)
7. **Manual test** for explicit triggers (power button -> correct service)
8. **Manual test** for conversation reload (power results re-render correctly)
