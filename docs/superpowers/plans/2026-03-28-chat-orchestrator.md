# Chat Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate HIJ, Competitor Finder, Idea Reality, and Co-Researcher into the Co-Work chatbot with full lab context, while keeping standalone versions untouched.

**Architecture:** Three-layer pipeline — Intent Gate (keyword + embedding) → LLM Tool-Use Router (GPT function-calling) → Parallel Executor (ThreadPoolExecutor) with adapter pattern wrapping existing services. Research profile cached on Tenant model. Frontend gets a powers trigger button, tabbed result cards, and loading states.

**Tech Stack:** Flask 3.0, Azure OpenAI (GPT-5, text-embedding-3-large), SQLAlchemy, ThreadPoolExecutor, Next.js 14, React 18, TypeScript, Tailwind CSS

**Spec:** `docs/superpowers/specs/2026-03-28-chat-orchestrator-design.md`

---

## File Structure

### New Backend Files
| File | Responsibility |
|------|---------------|
| `backend/services/chat_orchestrator/__init__.py` | Package init, exports orchestrate() entry point |
| `backend/services/chat_orchestrator/intent_gate.py` | Layer 1: keyword scan + embedding similarity gate |
| `backend/services/chat_orchestrator/context_injector.py` | RAG query + research profile loading |
| `backend/services/chat_orchestrator/tool_router.py` | Layer 2: LLM function-calling to select tools + extract params |
| `backend/services/chat_orchestrator/parallel_executor.py` | Layer 3: ThreadPoolExecutor, timeout management, result collection |
| `backend/services/chat_orchestrator/response_merger.py` | Final LLM call to generate personalized tabbed summaries |
| `backend/services/chat_orchestrator/adapters/__init__.py` | Shared SSE parser utility: parse_sse_stream() |
| `backend/services/chat_orchestrator/adapters/hij_adapter.py` | Wraps JournalScorerService.analyze_manuscript |
| `backend/services/chat_orchestrator/adapters/competitor_adapter.py` | Wraps CompetitorFinderService methods |
| `backend/services/chat_orchestrator/adapters/idea_adapter.py` | Wraps IdeaRealityService.check_idea |
| `backend/services/chat_orchestrator/adapters/co_researcher_adapter.py` | Wraps CoResearcherService (one-shot, no persistent session) |
| `backend/services/research_profile_service.py` | Lazy-built cached research profile per tenant |
| `backend/api/orchestrator_routes.py` | New blueprint: POST /api/chat/orchestrated |
| `backend/tests/test_intent_gate.py` | Unit tests for intent gate |
| `backend/tests/test_adapters.py` | Unit tests for all 4 adapters |
| `backend/tests/test_research_profile.py` | Unit tests for profile builder |
| `backend/tests/test_orchestrator.py` | Integration test for full pipeline |

### New Frontend Files
| File | Responsibility |
|------|---------------|
| `frontend/components/co-work/PowersTrigger.tsx` | Lightning bolt button + popover menu next to send arrow |
| `frontend/components/co-work/PowerResultCard.tsx` | Tabbed result card chat bubble with markdown summaries |
| `frontend/components/co-work/PowerLoadingCard.tsx` | Animated loading state showing service progress |
| `frontend/components/co-work/FullAnalysisPanel.tsx` | Right panel mode for full service results |

### Modified Files
| File | Changes |
|------|---------|
| `backend/database/models.py` | Add `research_profile` (JSON) + `profile_updated_at` + `profile_building` to Tenant; add `message_type` to ChatMessage |
| `backend/app_v2.py` | Register orchestrator_routes blueprint (~line 293) |
| `frontend/components/co-work/CoWorkChat.tsx` | Add PowersTrigger to input bar, SSE routing, PowerResultCard rendering |

---

## Task 1: Database Schema Changes

**Files:**
- Modify: `backend/database/models.py:209-261` (Tenant model), `backend/database/models.py:1596-1639` (ChatMessage model)

- [ ] **Step 1: Add columns to Tenant model**

In `backend/database/models.py`, add after line 236 (`is_active` column):

```python
    # Research profile (cached, lazy-built)
    research_profile = Column(JSON, nullable=True)
    profile_updated_at = Column(DateTime(timezone=True), nullable=True)
    profile_building = Column(Boolean, default=False)
```

- [ ] **Step 2: Add message_type to ChatMessage model**

In `backend/database/models.py`, add after line 1607 (`role` column):

```python
    message_type = Column(String(20), default='text')  # 'text' or 'power_result'
```

- [ ] **Step 3: Verify app starts with new columns**

Run:
```bash
cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work/backend
python -c "from database.models import Base, engine; Base.metadata.create_all(engine); print('Schema updated OK')"
```
Expected: `Schema updated OK`

- [ ] **Step 4: Commit**

```bash
cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work
git add backend/database/models.py
git commit -m "feat: add research_profile to Tenant and message_type to ChatMessage"
```

---

## Task 2: SSE Parser Utility + Adapter Base

**Files:**
- Create: `backend/services/chat_orchestrator/__init__.py`
- Create: `backend/services/chat_orchestrator/adapters/__init__.py`

- [ ] **Step 1: Create the orchestrator package**

Create `backend/services/chat_orchestrator/__init__.py`:

```python
"""Chat Orchestrator — routes user messages to specialized power services."""
```

- [ ] **Step 2: Create the shared SSE parser utility**

Create `backend/services/chat_orchestrator/adapters/__init__.py`:

```python
"""Adapter utilities for wrapping existing services."""

import json
import logging
from typing import Generator, List, Dict, Any

logger = logging.getLogger(__name__)


def parse_sse_stream(generator: Generator[str, None, None]) -> List[Dict[str, Any]]:
    """
    Consume an SSE generator and parse events into structured dicts.

    Existing services (HIJ, Competitor Finder) yield raw SSE strings like:
        "event: progress\\ndata: {...}\\n\\n"

    This collects all events and returns them as a list of parsed dicts:
        [{"event": "progress", "data": {...}}, ...]
    """
    events = []
    buffer = ""

    for chunk in generator:
        buffer += chunk

        # Split on double newline (SSE event boundary)
        while "\n\n" in buffer:
            event_str, buffer = buffer.split("\n\n", 1)
            event_data = _parse_single_sse_event(event_str.strip())
            if event_data:
                events.append(event_data)

    # Handle any remaining buffer
    if buffer.strip():
        event_data = _parse_single_sse_event(buffer.strip())
        if event_data:
            events.append(event_data)

    return events


def _parse_single_sse_event(event_str: str) -> Dict[str, Any] | None:
    """Parse a single SSE event string into {event, data}."""
    event_type = "message"
    data_lines = []

    for line in event_str.split("\n"):
        line = line.strip()
        if line.startswith("event:"):
            event_type = line[6:].strip()
        elif line.startswith("data:"):
            data_lines.append(line[5:].strip())

    if not data_lines:
        return None

    raw_data = "\n".join(data_lines)
    try:
        parsed_data = json.loads(raw_data)
    except json.JSONDecodeError:
        parsed_data = raw_data

    return {"event": event_type, "data": parsed_data}


def make_result_envelope(
    service: str,
    status: str = "success",
    summary: str | None = None,
    full_results: Dict | None = None,
    error: str | None = None,
) -> Dict[str, Any]:
    """Create a standardized result envelope for the parallel executor."""
    return {
        "service": service,
        "status": status,
        "summary": summary,
        "full_results": full_results,
        "error": error,
    }
```

- [ ] **Step 3: Commit**

```bash
cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work
git add backend/services/chat_orchestrator/
git commit -m "feat: add chat orchestrator package with SSE parser utility"
```

---

## Task 3: Service Adapters

**Files:**
- Create: `backend/services/chat_orchestrator/adapters/hij_adapter.py`
- Create: `backend/services/chat_orchestrator/adapters/competitor_adapter.py`
- Create: `backend/services/chat_orchestrator/adapters/idea_adapter.py`
- Create: `backend/services/chat_orchestrator/adapters/co_researcher_adapter.py`

- [ ] **Step 1: Write HIJ adapter**

Create `backend/services/chat_orchestrator/adapters/hij_adapter.py`:

```python
"""Adapter wrapping JournalScorerService for the orchestrator."""

import logging
from typing import Dict, Any, Optional

from services.journal_scorer_service import JournalScorerService
from . import parse_sse_stream, make_result_envelope

logger = logging.getLogger(__name__)


def run_hij(
    file_bytes: Optional[bytes] = None,
    filename: Optional[str] = None,
    raw_text: Optional[str] = None,
    context_package: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Run HIJ manuscript analysis and return a result envelope.

    Args:
        file_bytes: Raw bytes of the uploaded manuscript file
        filename: Original filename
        raw_text: Alternative text input (if no file)
        context_package: User's lab context (research_profile + relevant_chunks)

    Returns:
        Standardized result envelope with full_results containing parsed HIJ output
    """
    try:
        service = JournalScorerService()

        # Inject context hints into the analysis
        publication_year = None
        if context_package and context_package.get("research_profile"):
            profile = context_package["research_profile"]
            # Could use profile to hint field detection, but service handles this internally

        # Run the analysis pipeline
        generator = service.analyze_manuscript(
            file_bytes=file_bytes,
            filename=filename or "manuscript.pdf",
            raw_text=raw_text,
            user_publication_year=publication_year,
        )

        # Consume SSE generator into structured data
        events = parse_sse_stream(generator)

        # Extract key results from events
        full_results = _extract_hij_results(events)

        return make_result_envelope(
            service="hij",
            status="success",
            full_results=full_results,
        )

    except Exception as e:
        logger.error(f"HIJ adapter error: {e}", exc_info=True)
        return make_result_envelope(
            service="hij",
            status="error",
            error=f"Manuscript analysis failed: {str(e)}",
        )


def _extract_hij_results(events: list) -> Dict[str, Any]:
    """Extract structured results from parsed SSE events."""
    results = {
        "scores": None,
        "journal_matches": None,
        "red_flags": None,
        "field_detection": None,
        "citations": None,
        "recommendations": None,
        "raw_events": [],
    }

    for event in events:
        event_type = event.get("event", "")
        data = event.get("data", {})

        if isinstance(data, dict):
            results["raw_events"].append(event)

            if event_type == "scores" or "score" in str(data.get("type", "")):
                results["scores"] = data
            elif event_type == "journals" or "journal" in str(data.get("type", "")):
                results["journal_matches"] = data
            elif event_type == "red_flags" or "red_flag" in str(data.get("type", "")):
                results["red_flags"] = data
            elif event_type == "field" or "field" in str(data.get("type", "")):
                results["field_detection"] = data
            elif event_type == "citations":
                results["citations"] = data
            elif event_type == "recommendations" or event_type == "final":
                results["recommendations"] = data

    return results
```

- [ ] **Step 2: Write Competitor Finder adapter**

Create `backend/services/chat_orchestrator/adapters/competitor_adapter.py`:

```python
"""Adapter wrapping CompetitorFinderService for the orchestrator."""

import logging
from typing import Dict, Any, Optional, List

from services.competitor_finder_service import CompetitorFinderService
from . import make_result_envelope

logger = logging.getLogger(__name__)


def run_competitor_finder(
    topics: Optional[List[str]] = None,
    field: Optional[str] = None,
    paper_text: Optional[str] = None,
    context_package: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Run competitor search and return a result envelope.

    Args:
        topics: Explicit search topics
        field: Research field
        paper_text: Full paper text (for topic extraction)
        context_package: User's lab context

    Returns:
        Standardized result envelope
    """
    try:
        service = CompetitorFinderService()

        # Use context to enhance search
        keywords = None
        if context_package and context_package.get("research_profile"):
            profile = context_package["research_profile"]
            if not field and profile.get("primary_fields"):
                field = profile["primary_fields"][0]
            if not topics and profile.get("recent_topics"):
                topics = profile["recent_topics"][:3]

        # Extract topics from paper text if not provided
        if paper_text:
            topic_info = service._extract_topic(paper_text, field or "", keywords)
        elif topics:
            topic_info = {
                "topic": topics[0] if topics else "",
                "search_queries": topics,
                "key_terms": topics,
                "field": field or "",
                "arxiv_categories": [],
            }
        else:
            return make_result_envelope(
                service="competitor_finder",
                status="error",
                error="No topics or paper text provided for competitor search.",
            )

        # Run searches
        openalex_results = service._search_openalex(topic_info)
        arxiv_results = service._search_arxiv(topic_info)
        nih_results = service._search_nih(topic_info)

        # Calculate urgency
        total_competitors = len(openalex_results) + len(arxiv_results) + len(nih_results)
        if total_competitors > 15:
            urgency = "HIGH"
        elif total_competitors > 8:
            urgency = "MEDIUM-HIGH"
        elif total_competitors > 4:
            urgency = "MEDIUM"
        else:
            urgency = "LOW"

        full_results = {
            "topic_info": topic_info,
            "competing_labs": openalex_results,
            "preprints": arxiv_results,
            "active_grants": nih_results,
            "urgency": urgency,
            "total_competitors": total_competitors,
        }

        return make_result_envelope(
            service="competitor_finder",
            status="success",
            full_results=full_results,
        )

    except Exception as e:
        logger.error(f"Competitor finder adapter error: {e}", exc_info=True)
        return make_result_envelope(
            service="competitor_finder",
            status="error",
            error=f"Competitor search failed: {str(e)}",
        )
```

- [ ] **Step 3: Write Idea Reality adapter**

Create `backend/services/chat_orchestrator/adapters/idea_adapter.py`:

```python
"""Adapter wrapping IdeaRealityService for the orchestrator."""

import logging
from typing import Dict, Any, Optional

from services.idea_reality_service import IdeaRealityService
from . import make_result_envelope

logger = logging.getLogger(__name__)


def run_idea_reality(
    idea_description: str,
    context_package: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    Run idea validation and return a result envelope.

    Args:
        idea_description: Description of the research idea
        context_package: User's lab context (used to filter self-matches)

    Returns:
        Standardized result envelope
    """
    try:
        service = IdeaRealityService()
        result = service.check_idea(idea_description)

        # Filter out user's own repos/work if we have context
        if context_package and context_package.get("research_profile"):
            profile = context_package["research_profile"]
            institution = profile.get("institution", "").lower()
            if institution and result.get("competitors"):
                result["competitors"] = [
                    c for c in result["competitors"]
                    if institution not in (c.get("owner", "") or "").lower()
                ]

        return make_result_envelope(
            service="idea_reality",
            status="success",
            full_results=result,
        )

    except Exception as e:
        logger.error(f"Idea reality adapter error: {e}", exc_info=True)
        return make_result_envelope(
            service="idea_reality",
            status="error",
            error=f"Idea validation failed: {str(e)}",
        )
```

- [ ] **Step 4: Write Co-Researcher adapter**

Create `backend/services/chat_orchestrator/adapters/co_researcher_adapter.py`:

```python
"""Adapter wrapping CoResearcherService for the orchestrator (one-shot, no persistent session)."""

import logging
from typing import Dict, Any, Optional

from services.co_researcher_service import CoResearcherService
from . import parse_sse_stream, make_result_envelope

logger = logging.getLogger(__name__)


def run_co_researcher(
    research_question: str,
    paper_text: Optional[str] = None,
    protocol_text: Optional[str] = None,
    context_package: Optional[Dict] = None,
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run co-researcher analysis as a one-shot call (no persistent session).

    Args:
        research_question: The user's research question
        paper_text: Optional paper text for context
        protocol_text: Optional protocol text for context
        context_package: User's lab context
        tenant_id: User's tenant ID

    Returns:
        Standardized result envelope
    """
    try:
        service = CoResearcherService()

        # Build an enriched message with context
        enriched_message = research_question

        if context_package and context_package.get("research_profile"):
            profile = context_package["research_profile"]
            fields = ", ".join(profile.get("primary_fields", []))
            topics = ", ".join(profile.get("recent_topics", []))
            if fields or topics:
                enriched_message = (
                    f"[Research context: fields={fields}, recent topics={topics}]\n\n"
                    f"{research_question}"
                )

        if paper_text:
            enriched_message += f"\n\n[Paper excerpt]: {paper_text[:3000]}"
        if protocol_text:
            enriched_message += f"\n\n[Protocol excerpt]: {protocol_text[:3000]}"

        # Use the service's OpenAI client directly for a one-shot analysis
        # rather than creating a persistent research session
        from azure_openai_config import get_azure_client, AZURE_CHAT_DEPLOYMENT
        client = get_azure_client()

        response = client.chat.completions.create(
            model=AZURE_CHAT_DEPLOYMENT,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a research co-pilot. Given the user's research question and context, "
                        "generate 3-5 structured research hypotheses. For each hypothesis provide:\n"
                        "1. Title\n2. Description\n3. Methodology approach\n"
                        "4. Expected outcome\n5. Risk assessment (low/medium/high)\n"
                        "6. Implementation steps (3-5 concrete steps)\n"
                        "Format as JSON array."
                    ),
                },
                {"role": "user", "content": enriched_message},
            ],
            temperature=0.8,
            max_tokens=3000,
        )

        import json
        raw_text = response.choices[0].message.content

        # Try to parse JSON from the response
        try:
            # Strip markdown code fences if present
            clean = raw_text.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1]
                clean = clean.rsplit("```", 1)[0]
            hypotheses = json.loads(clean)
        except json.JSONDecodeError:
            hypotheses = [{"title": "Research Analysis", "description": raw_text}]

        full_results = {
            "hypotheses": hypotheses,
            "research_question": research_question,
            "context_used": bool(context_package),
        }

        return make_result_envelope(
            service="co_researcher",
            status="success",
            full_results=full_results,
        )

    except Exception as e:
        logger.error(f"Co-researcher adapter error: {e}", exc_info=True)
        return make_result_envelope(
            service="co_researcher",
            status="error",
            error=f"Research analysis failed: {str(e)}",
        )
```

- [ ] **Step 5: Commit**

```bash
cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work
git add backend/services/chat_orchestrator/adapters/
git commit -m "feat: add service adapters for HIJ, Competitor Finder, Idea Reality, Co-Researcher"
```

---

## Task 4: Intent Gate (Layer 1)

**Files:**
- Create: `backend/services/chat_orchestrator/intent_gate.py`
- Create: `backend/tests/test_intent_gate.py`

- [ ] **Step 1: Write intent gate tests**

Create `backend/tests/test_intent_gate.py`:

```python
"""Tests for the Intent Gate (Layer 1)."""

import pytest
from services.chat_orchestrator.intent_gate import IntentGate


@pytest.fixture
def gate():
    return IntentGate()


class TestKeywordDetection:
    def test_hij_keywords(self, gate):
        result = gate.classify("Can you score my manuscript for Nature?")
        assert "hij" in result["powers"]

    def test_competitor_keywords(self, gate):
        result = gate.classify("Find competitors in CRISPR delivery")
        assert "competitor_finder" in result["powers"]

    def test_idea_keywords(self, gate):
        result = gate.classify("Is this idea novel? Validate my research concept")
        assert "idea_reality" in result["powers"]

    def test_co_researcher_keywords(self, gate):
        result = gate.classify("Help me brainstorm research hypotheses")
        assert "co_researcher" in result["powers"]

    def test_no_power_detected(self, gate):
        result = gate.classify("What was discussed in yesterday's meeting?")
        assert result["powers"] == []
        assert result["needs_powers"] is False

    def test_multi_intent(self, gate):
        result = gate.classify("Score my paper and find competitors")
        assert "hij" in result["powers"]
        assert "competitor_finder" in result["powers"]

    def test_explicit_trigger_bypass(self, gate):
        result = gate.classify("analyze this", power_hint="hij")
        assert result["powers"] == ["hij"]
        assert result["needs_powers"] is True
        assert result["skip_router"] is True


class TestClassifyOutput:
    def test_output_shape(self, gate):
        result = gate.classify("Score my manuscript")
        assert "needs_powers" in result
        assert "powers" in result
        assert "skip_router" in result
        assert isinstance(result["powers"], list)
        assert isinstance(result["needs_powers"], bool)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work/backend
python -m pytest tests/test_intent_gate.py -v 2>&1 | head -30
```
Expected: FAIL (module not found)

- [ ] **Step 3: Write intent gate implementation**

Create `backend/services/chat_orchestrator/intent_gate.py`:

```python
"""Layer 1: Intent Gate — fast triage for power service routing."""

import os
import re
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Keyword patterns for each power service
POWER_PATTERNS: Dict[str, List[str]] = {
    "hij": [
        r"\bscore\b.*\b(paper|manuscript|article)\b",
        r"\bmanuscript\b",
        r"\bjournal\s+match",
        r"\bimpact\s+factor\b",
        r"\bred\s+flags?\b.*\b(paper|manuscript)\b",
        r"\breview\s+my\s+paper\b",
        r"\bpublish\b",
        r"\bwhere\s+should\s+I\s+submit\b",
        r"\bscore\s+(my|this|the)\b",
        r"\bjournal\s+recommend",
        r"\bmanuscript\s+(scor|analys|evaluat)",
    ],
    "competitor_finder": [
        r"\bcompetitor",
        r"\bcompeting\s+lab",
        r"\bwho\s+else\s+(is|are)\s+working",
        r"\bgrants?\s+in\s+my\s+area\b",
        r"\bpreprints?\b.*\b(similar|competing|related)\b",
        r"\bsimilar\s+research\b",
        r"\bcompetition\b.*\bresearch\b",
        r"\bwho\s+(is|are)\s+researching\b",
        r"\bcompeting\s+(groups?|teams?|labs?)\b",
    ],
    "idea_reality": [
        r"\bvalidate\s+(my\s+)?idea\b",
        r"\bis\s+this\s+novel\b",
        r"\bdoes\s+this\s+exist\b",
        r"\breality\s+check\b",
        r"\bfeasib(le|ility)\b.*\b(idea|concept|research)\b",
        r"\bhas\s+anyone\s+done\b",
        r"\bnovel(ty)?\b.*\b(check|assess|evaluat)\b",
        r"\balready\s+(been\s+)?done\b",
        r"\boriginal(ity)?\b.*\b(check|research)\b",
    ],
    "co_researcher": [
        r"\bhypothes[ie]s\b",
        r"\bbrainstorm\s+research\b",
        r"\bagent\s+debate\b",
        r"\bco[\-\s]?research",
        r"\bresearch\s+direction",
        r"\bresearch\s+idea",
        r"\bgenerate\s+(research\s+)?hypothes",
        r"\bexplore\s+research\b",
    ],
}

# Pre-compile all patterns
_COMPILED_PATTERNS: Dict[str, List[re.Pattern]] = {
    power: [re.compile(p, re.IGNORECASE) for p in patterns]
    for power, patterns in POWER_PATTERNS.items()
}


class IntentGate:
    """
    Layer 1 of the Chat Orchestrator.

    Fast keyword-based triage to determine if a message needs power services.
    Falls back to embedding similarity for ambiguous messages.
    """

    def __init__(self):
        self._embedding_client = None
        self._power_embeddings = None
        self.similarity_threshold = float(
            os.getenv("POWER_INTENT_THRESHOLD", "0.75")
        )

    def classify(
        self,
        message: str,
        power_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Classify a message to determine if it needs power services.

        Args:
            message: The user's chat message
            power_hint: Explicit power trigger from UI (skips classification)

        Returns:
            {
                "needs_powers": bool,
                "powers": List[str],  # e.g., ["hij", "competitor_finder"]
                "skip_router": bool,  # True if power_hint set (skip Layer 2)
            }
        """
        # Explicit trigger bypass
        if power_hint:
            valid_powers = {"hij", "competitor_finder", "idea_reality", "co_researcher"}
            if power_hint in valid_powers:
                return {
                    "needs_powers": True,
                    "powers": [power_hint],
                    "skip_router": True,
                }

        # Stage 1: Keyword/regex scan (< 1ms)
        detected = self._keyword_scan(message)

        if detected:
            return {
                "needs_powers": True,
                "powers": detected,
                "skip_router": len(detected) == 1,  # Skip router for single clear intent
            }

        # Stage 2: Embedding similarity fallback (~200ms)
        detected = self._embedding_scan(message)

        if detected:
            return {
                "needs_powers": True,
                "powers": detected,
                "skip_router": False,  # Ambiguous — let router decide
            }

        # No powers detected
        return {
            "needs_powers": False,
            "powers": [],
            "skip_router": False,
        }

    def _keyword_scan(self, message: str) -> List[str]:
        """Fast keyword/regex scan against known trigger patterns."""
        detected = []
        for power, patterns in _COMPILED_PATTERNS.items():
            for pattern in patterns:
                if pattern.search(message):
                    detected.append(power)
                    break  # One match per power is enough
        return detected

    def _embedding_scan(self, message: str) -> List[str]:
        """
        Fallback: compute message embedding and compare against power descriptions.
        Only runs if keyword scan found nothing.
        """
        try:
            self._ensure_embeddings_loaded()

            if not self._embedding_client or not self._power_embeddings:
                return []

            from azure_openai_config import get_embedding
            msg_embedding = get_embedding(message)

            detected = []
            for power, power_emb in self._power_embeddings.items():
                similarity = self._cosine_similarity(msg_embedding, power_emb)
                if similarity >= self.similarity_threshold:
                    detected.append(power)

            return detected

        except Exception as e:
            logger.warning(f"Embedding scan failed, falling back to no powers: {e}")
            return []

    def _ensure_embeddings_loaded(self):
        """Lazy-load power description embeddings (computed once)."""
        if self._power_embeddings is not None:
            return

        try:
            from azure_openai_config import get_embedding

            power_descriptions = {
                "hij": (
                    "Score and evaluate a research manuscript or paper for journal publication. "
                    "Analyze methodology, impact, citations, and match to journals."
                ),
                "competitor_finder": (
                    "Find competing research labs, preprints, and grants in a specific "
                    "research area or field. Identify who else is working on similar topics."
                ),
                "idea_reality": (
                    "Validate a research idea for novelty. Check if similar implementations "
                    "or projects already exist on GitHub, PyPI, or the web."
                ),
                "co_researcher": (
                    "Generate research hypotheses and brainstorm new research directions. "
                    "Explore potential experiments and methodological approaches."
                ),
            }

            self._power_embeddings = {}
            for power, desc in power_descriptions.items():
                self._power_embeddings[power] = get_embedding(desc)

            self._embedding_client = True
            logger.info("Power description embeddings loaded successfully")

        except Exception as e:
            logger.warning(f"Failed to load power embeddings: {e}")
            self._embedding_client = False
            self._power_embeddings = {}

    @staticmethod
    def _cosine_similarity(vec_a: list, vec_b: list) -> float:
        """Compute cosine similarity between two vectors."""
        dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = sum(a * a for a in vec_a) ** 0.5
        norm_b = sum(b * b for b in vec_b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work/backend
python -m pytest tests/test_intent_gate.py -v
```
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work
git add backend/services/chat_orchestrator/intent_gate.py backend/tests/test_intent_gate.py
git commit -m "feat: add intent gate (Layer 1) with keyword scan + embedding fallback"
```

---

## Task 5: Research Profile Service

**Files:**
- Create: `backend/services/research_profile_service.py`

- [ ] **Step 1: Write research profile service**

Create `backend/services/research_profile_service.py`:

```python
"""
Research Profile Service — lazy-built cached research profile per tenant.

Aggregates the user's documents' structured_summary fields into a concise
research profile used for context injection in the orchestrator.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

from database.models import SessionLocal, Tenant, Document
from azure_openai_config import get_azure_client, AZURE_CHAT_DEPLOYMENT

logger = logging.getLogger(__name__)

PROFILE_STALE_HOURS = 24


def get_or_build_profile(tenant_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the cached research profile for a tenant, rebuilding if stale.

    Returns None if the tenant has no documents or profile can't be built.
    Uses a building flag to prevent concurrent rebuilds.
    """
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            return None

        # Check if profile is fresh enough
        if tenant.research_profile and tenant.profile_updated_at:
            age = datetime.now(timezone.utc) - tenant.profile_updated_at
            if age < timedelta(hours=PROFILE_STALE_HOURS):
                return tenant.research_profile

        # Check if another request is already building
        if tenant.profile_building:
            # Return stale profile rather than waiting
            return tenant.research_profile

        # Mark as building
        tenant.profile_building = True
        db.commit()

        try:
            profile = _build_profile(tenant_id, db)
            if profile is not None:
                tenant.research_profile = profile
                tenant.profile_updated_at = datetime.now(timezone.utc)
            tenant.profile_building = False
            db.commit()
            return profile
        except Exception as e:
            logger.error(f"Failed to build research profile for {tenant_id}: {e}")
            tenant.profile_building = False
            db.commit()
            return tenant.research_profile  # Return stale if available

    finally:
        db.close()


def _build_profile(tenant_id: str, db) -> Dict[str, Any]:
    """
    Build a research profile by aggregating the tenant's recent documents.

    Uses structured_summary JSON from documents (already extracted during sync
    by extraction_service.py) to avoid re-processing raw content.
    """
    # Get the 20 most recent documents with structured summaries
    docs = (
        db.query(Document)
        .filter(
            Document.tenant_id == tenant_id,
            Document.structured_summary.isnot(None),
        )
        .order_by(Document.created_at.desc())
        .limit(20)
        .all()
    )

    if not docs:
        return None  # Caller must NOT update profile_updated_at when result is None

    # Collect summaries for the LLM
    summaries = []
    for doc in docs:
        summary = doc.structured_summary
        if isinstance(summary, str):
            try:
                summary = json.loads(summary)
            except json.JSONDecodeError:
                summary = {"text": summary}

        summaries.append({
            "title": doc.title or "Untitled",
            "source": doc.source if hasattr(doc, "source") else "unknown",
            "summary": summary,
        })

    # Use LLM to synthesize a research profile
    client = get_azure_client()

    response = client.chat.completions.create(
        model=AZURE_CHAT_DEPLOYMENT,
        messages=[
            {
                "role": "system",
                "content": (
                    "Analyze these document summaries from a researcher's knowledge base. "
                    "Extract a concise research profile as JSON with these fields:\n"
                    "- primary_fields: array of 1-3 research fields\n"
                    "- recent_topics: array of 3-5 specific topics they work on\n"
                    "- institution: their institution name (if detectable, else null)\n"
                    "- collaborators: array of collaborator names (if detectable, else [])\n"
                    "- recent_papers: array of their paper titles (if any, else [])\n"
                    "- methodology_preferences: array of methods they commonly use\n"
                    "Return ONLY valid JSON, no markdown."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(summaries[:20], default=str),
            },
        ],
        temperature=0.3,
        max_tokens=1000,
    )

    raw = response.choices[0].message.content.strip()

    # Parse the JSON response
    try:
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        profile = json.loads(raw)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse research profile JSON: {raw[:200]}")
        profile = {
            "primary_fields": [],
            "recent_topics": [],
            "institution": None,
            "collaborators": [],
            "recent_papers": [],
            "methodology_preferences": [],
        }

    profile["updated_at"] = datetime.now(timezone.utc).isoformat()
    return profile
```

- [ ] **Step 2: Commit**

```bash
cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work
git add backend/services/research_profile_service.py
git commit -m "feat: add research profile service with lazy-build and caching"
```

---

## Task 6: Context Injector

**Files:**
- Create: `backend/services/chat_orchestrator/context_injector.py`

- [ ] **Step 1: Write context injector**

Create `backend/services/chat_orchestrator/context_injector.py`:

```python
"""Context Injector — pulls RAG chunks + research profile for power services."""

import logging
from typing import Dict, Any, Optional, List

from services.research_profile_service import get_or_build_profile

logger = logging.getLogger(__name__)


def inject_context(
    tenant_id: str,
    message: str,
    source_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Build the context package for power services.

    Args:
        tenant_id: The user's tenant ID
        message: The user's chat message (used as RAG query)
        source_types: Optional filter for document sources

    Returns:
        {
            "research_profile": {...} or None,
            "relevant_chunks": [...] list of text chunks from RAG,
            "profile_fields": [...] shorthand for SSE event,
            "chunks_found": int,
        }
    """
    # 1. Get or build research profile
    research_profile = get_or_build_profile(tenant_id)

    # 2. RAG query for relevant chunks
    relevant_chunks = _query_rag(tenant_id, message, source_types)

    # Build context package
    profile_fields = []
    if research_profile:
        profile_fields = research_profile.get("primary_fields", [])

    return {
        "research_profile": research_profile,
        "relevant_chunks": relevant_chunks,
        "profile_fields": profile_fields,
        "chunks_found": len(relevant_chunks),
    }


def _query_rag(
    tenant_id: str,
    query: str,
    source_types: Optional[List[str]] = None,
    top_k: int = 15,
) -> List[Dict[str, Any]]:
    """Query the existing Pinecone RAG pipeline for relevant chunks."""
    try:
        from vector_stores.pinecone_store import PineconeVectorStore

        store = PineconeVectorStore()
        results = store.search(
            query=query,
            tenant_id=tenant_id,
            top_k=top_k,
        )

        chunks = []
        for result in results:
            chunks.append({
                "text": result.get("text", result.get("content", "")),
                "score": result.get("score", 0),
                "source": result.get("metadata", {}).get("source_type", "unknown"),  # matches Document.source_type
                "document_id": result.get("metadata", {}).get("document_id"),
            })

        return chunks

    except Exception as e:
        logger.warning(f"RAG query failed for tenant {tenant_id}: {e}")
        return []
```

- [ ] **Step 2: Commit**

```bash
cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work
git add backend/services/chat_orchestrator/context_injector.py
git commit -m "feat: add context injector with RAG + research profile loading"
```

---

## Task 7: Tool Router (Layer 2)

**Files:**
- Create: `backend/services/chat_orchestrator/tool_router.py`

- [ ] **Step 1: Write tool router**

Create `backend/services/chat_orchestrator/tool_router.py`:

```python
"""Layer 2: LLM Tool-Use Router — uses GPT function-calling to select tools and extract params."""

import json
import logging
from typing import Dict, Any, List, Optional

from azure_openai_config import get_azure_client, AZURE_CHAT_DEPLOYMENT

logger = logging.getLogger(__name__)

# Tool definitions for GPT function-calling
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "score_manuscript",
            "description": (
                "Score and evaluate a research manuscript for journal publication. "
                "Analyzes methodology, impact, citations, red flags, and recommends journals."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "paper_text": {
                        "type": "string",
                        "description": "The text content of the paper/manuscript to score",
                    },
                    "focus_areas": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional specific areas to focus the analysis on",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_competitors",
            "description": (
                "Find competing research labs, recent preprints, and active grants "
                "in a research area. Searches OpenAlex, arXiv, and NIH Reporter."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "topics": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Research topics to search for competitors",
                    },
                    "field": {
                        "type": "string",
                        "description": "Broad research field (e.g., 'molecular biology')",
                    },
                },
                "required": ["topics"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_idea",
            "description": (
                "Validate a research idea for novelty by checking GitHub, PyPI, "
                "and web sources for existing implementations."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "idea_description": {
                        "type": "string",
                        "description": "Description of the research idea to validate",
                    },
                    "domain": {
                        "type": "string",
                        "description": "Research domain for context",
                    },
                },
                "required": ["idea_description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_co_researcher",
            "description": (
                "Generate research hypotheses and brainstorm new research directions "
                "based on a question, paper, or protocol."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "research_question": {
                        "type": "string",
                        "description": "The research question to explore",
                    },
                    "paper_text": {
                        "type": "string",
                        "description": "Optional paper text for context",
                    },
                    "protocol_text": {
                        "type": "string",
                        "description": "Optional protocol text for context",
                    },
                },
                "required": ["research_question"],
            },
        },
    },
]

# Map tool names to adapter service names
TOOL_TO_SERVICE = {
    "score_manuscript": "hij",
    "find_competitors": "competitor_finder",
    "validate_idea": "idea_reality",
    "run_co_researcher": "co_researcher",
}


def route(
    message: str,
    context_package: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Use LLM function-calling to decide which tools to invoke and extract parameters.

    Args:
        message: The user's chat message
        context_package: Research profile + RAG chunks for context

    Returns:
        List of tool calls: [{"service": "hij", "args": {...}}, ...]
    """
    try:
        client = get_azure_client()

        # Build context string for the system prompt
        context_str = ""
        if context_package and context_package.get("research_profile"):
            profile = context_package["research_profile"]
            fields = ", ".join(profile.get("primary_fields", []))
            topics = ", ".join(profile.get("recent_topics", []))
            context_str = f"\nUser's research context: fields={fields}, topics={topics}"

        response = client.chat.completions.create(
            model=AZURE_CHAT_DEPLOYMENT,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a research assistant router. Analyze the user's message "
                        "and decide which research tools to invoke. You may call multiple "
                        "tools if the user's request spans multiple tasks. Extract the "
                        "relevant parameters from their message for each tool call."
                        f"{context_str}"
                    ),
                },
                {"role": "user", "content": message},
            ],
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
            temperature=0,
            max_tokens=500,
        )

        # Parse tool calls from response
        tool_calls = []
        msg = response.choices[0].message

        if msg.tool_calls:
            for tc in msg.tool_calls:
                service = TOOL_TO_SERVICE.get(tc.function.name)
                if service:
                    try:
                        args = json.loads(tc.function.arguments)
                    except json.JSONDecodeError:
                        args = {}

                    tool_calls.append({
                        "service": service,
                        "tool_name": tc.function.name,
                        "args": args,
                    })

        if not tool_calls:
            logger.info(f"Tool router found no tools for message: {message[:100]}")

        return tool_calls

    except Exception as e:
        logger.error(f"Tool router error: {e}", exc_info=True)
        return []


def extract_params_simple(
    message: str,
    power: str,
    context_package: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Lightweight parameter extraction for explicit triggers (skips full tool-use router).

    Used when power_hint is set and we know the target service — just need to extract
    the relevant parameters from the message.
    """
    args = {}

    if power == "hij":
        # For HIJ, the paper text comes from file upload — args are minimal
        args = {"paper_text": message if len(message) > 200 else None}

    elif power == "competitor_finder":
        # Extract topics from the message
        topics = [t.strip() for t in message.split(",") if len(t.strip()) > 3]
        if not topics:
            topics = [message[:200]]

        field = None
        if context_package and context_package.get("research_profile"):
            fields = context_package["research_profile"].get("primary_fields", [])
            field = fields[0] if fields else None

        args = {"topics": topics, "field": field}

    elif power == "idea_reality":
        args = {"idea_description": message}

    elif power == "co_researcher":
        args = {"research_question": message}

    return args
```

- [ ] **Step 2: Commit**

```bash
cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work
git add backend/services/chat_orchestrator/tool_router.py
git commit -m "feat: add LLM tool-use router (Layer 2) with function-calling"
```

---

## Task 8: Parallel Executor (Layer 3)

**Files:**
- Create: `backend/services/chat_orchestrator/parallel_executor.py`

- [ ] **Step 1: Write parallel executor**

Create `backend/services/chat_orchestrator/parallel_executor.py`:

```python
"""Layer 3: Parallel Executor — runs multiple service adapters concurrently."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from typing import Dict, Any, List, Optional, Callable

logger = logging.getLogger(__name__)

# Timeout configuration
PER_SERVICE_TIMEOUT = 90   # seconds per individual service
TOTAL_TIMEOUT = 120        # wall-clock timeout for entire fan-out

# Map service names to adapter functions
_ADAPTER_REGISTRY: Dict[str, Callable] = {}


def _register_adapters():
    """Lazy-load adapter functions to avoid circular imports."""
    global _ADAPTER_REGISTRY
    if _ADAPTER_REGISTRY:
        return

    from .adapters.hij_adapter import run_hij
    from .adapters.competitor_adapter import run_competitor_finder
    from .adapters.idea_adapter import run_idea_reality
    from .adapters.co_researcher_adapter import run_co_researcher

    _ADAPTER_REGISTRY = {
        "hij": run_hij,
        "competitor_finder": run_competitor_finder,
        "idea_reality": run_idea_reality,
        "co_researcher": run_co_researcher,
    }


def execute(
    tool_calls: List[Dict[str, Any]],
    context_package: Optional[Dict[str, Any]] = None,
    file_bytes: Optional[bytes] = None,
    filename: Optional[str] = None,
    tenant_id: Optional[str] = None,
    on_service_start: Optional[Callable] = None,
    on_service_complete: Optional[Callable] = None,
) -> List[Dict[str, Any]]:
    """
    Execute multiple service adapters in parallel using ThreadPoolExecutor.

    Args:
        tool_calls: List of {"service": str, "args": dict} from the router
        context_package: Research profile + RAG chunks
        file_bytes: Optional uploaded file bytes
        filename: Optional uploaded filename
        tenant_id: User's tenant ID
        on_service_start: Callback(service_name) when a service begins
        on_service_complete: Callback(service_name, status) when a service finishes

    Returns:
        List of result envelopes from adapters
    """
    _register_adapters()

    if not tool_calls:
        return []

    results = []

    # Build tasks
    tasks = []
    for tc in tool_calls:
        service = tc["service"]
        args = tc.get("args", {})

        adapter_fn = _ADAPTER_REGISTRY.get(service)
        if not adapter_fn:
            logger.warning(f"No adapter registered for service: {service}")
            continue

        # Build adapter kwargs
        kwargs = _build_adapter_kwargs(
            service=service,
            args=args,
            context_package=context_package,
            file_bytes=file_bytes,
            filename=filename,
            tenant_id=tenant_id,
        )

        tasks.append((service, adapter_fn, kwargs))

    if not tasks:
        return []

    # Execute in parallel
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        future_to_service = {}

        for service, adapter_fn, kwargs in tasks:
            if on_service_start:
                on_service_start(service)

            future = executor.submit(adapter_fn, **kwargs)
            future_to_service[future] = service

        # Collect results with timeout
        try:
            for future in as_completed(future_to_service, timeout=TOTAL_TIMEOUT):
                service = future_to_service[future]
                try:
                    result = future.result(timeout=PER_SERVICE_TIMEOUT)
                    results.append(result)

                    if on_service_complete:
                        on_service_complete(service, result.get("status", "success"))

                except TimeoutError:
                    logger.warning(f"Service {service} timed out")
                    from .adapters import make_result_envelope
                    results.append(make_result_envelope(
                        service=service,
                        status="timeout",
                        error=f"Service timed out after {PER_SERVICE_TIMEOUT}s. Try the standalone version.",
                    ))
                    if on_service_complete:
                        on_service_complete(service, "timeout")

                except Exception as e:
                    logger.error(f"Service {service} failed: {e}", exc_info=True)
                    from .adapters import make_result_envelope
                    results.append(make_result_envelope(
                        service=service,
                        status="error",
                        error=str(e),
                    ))
                    if on_service_complete:
                        on_service_complete(service, "error")

        except TimeoutError:
            # Total timeout exceeded — collect whatever finished
            logger.warning("Total execution timeout exceeded")
            for future, service in future_to_service.items():
                if not future.done():
                    from .adapters import make_result_envelope
                    results.append(make_result_envelope(
                        service=service,
                        status="timeout",
                        error="Overall timeout exceeded.",
                    ))

    return results


def _build_adapter_kwargs(
    service: str,
    args: Dict[str, Any],
    context_package: Optional[Dict],
    file_bytes: Optional[bytes],
    filename: Optional[str],
    tenant_id: Optional[str],
) -> Dict[str, Any]:
    """Build the kwargs dict for a specific adapter function."""
    kwargs = {"context_package": context_package}

    if service == "hij":
        kwargs["file_bytes"] = file_bytes
        kwargs["filename"] = filename
        kwargs["raw_text"] = args.get("paper_text")

    elif service == "competitor_finder":
        kwargs["topics"] = args.get("topics")
        kwargs["field"] = args.get("field")
        kwargs["paper_text"] = args.get("paper_text")

    elif service == "idea_reality":
        kwargs["idea_description"] = args.get("idea_description", "")

    elif service == "co_researcher":
        kwargs["research_question"] = args.get("research_question", "")
        kwargs["paper_text"] = args.get("paper_text")
        kwargs["protocol_text"] = args.get("protocol_text")
        kwargs["tenant_id"] = tenant_id

    return kwargs
```

- [ ] **Step 2: Commit**

```bash
cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work
git add backend/services/chat_orchestrator/parallel_executor.py
git commit -m "feat: add parallel executor (Layer 3) with ThreadPoolExecutor"
```

---

## Task 9: Response Merger

**Files:**
- Create: `backend/services/chat_orchestrator/response_merger.py`

- [ ] **Step 1: Write response merger**

Create `backend/services/chat_orchestrator/response_merger.py`:

```python
"""Response Merger — generates personalized tabbed summaries from service results."""

import json
import logging
from typing import Dict, Any, List, Optional

from azure_openai_config import get_azure_client, AZURE_CHAT_DEPLOYMENT

logger = logging.getLogger(__name__)

SERVICE_LABELS = {
    "hij": {"label": "Manuscript Score", "icon": "file-text"},
    "competitor_finder": {"label": "Competitors", "icon": "search"},
    "idea_reality": {"label": "Idea Check", "icon": "lightbulb"},
    "co_researcher": {"label": "Co-Researcher", "icon": "flask-conical"},
}


def merge(
    results: List[Dict[str, Any]],
    research_profile: Optional[Dict] = None,
    user_message: str = "",
) -> Dict[str, Any]:
    """
    Merge multiple service results into a tabbed response with personalized summaries.

    Args:
        results: List of result envelopes from parallel executor
        research_profile: User's cached research profile
        user_message: Original user message for context

    Returns:
        {
            "type": "power_result",
            "tabs": [...],
            "followup_suggestions": [...]
        }
    """
    if not results:
        return {
            "type": "power_result",
            "tabs": [],
            "followup_suggestions": [],
        }

    tabs = []
    successful_results = []

    for result in results:
        service = result["service"]
        meta = SERVICE_LABELS.get(service, {"label": service, "icon": "zap"})

        if result["status"] != "success":
            # Error/timeout tab
            tabs.append({
                "label": meta["label"],
                "icon": meta["icon"],
                "status": result["status"],
                "summary": result.get("error", "Service unavailable. Try the standalone version."),
                "full_results": None,
            })
        else:
            successful_results.append(result)
            tabs.append({
                "label": meta["label"],
                "icon": meta["icon"],
                "status": "success",
                "summary": None,  # Will be filled by LLM
                "full_results": result.get("full_results"),
            })

    # Generate personalized summaries for successful tabs
    if successful_results:
        summaries = _generate_summaries(successful_results, research_profile, user_message)

        # Attach summaries to tabs
        summary_idx = 0
        for tab in tabs:
            if tab["status"] == "success" and summary_idx < len(summaries):
                tab["summary"] = summaries[summary_idx]
                summary_idx += 1

    # Generate followup suggestions
    followup_suggestions = _generate_followups(results, research_profile)

    return {
        "type": "power_result",
        "tabs": tabs,
        "followup_suggestions": followup_suggestions,
    }


def _generate_summaries(
    results: List[Dict],
    research_profile: Optional[Dict],
    user_message: str,
) -> List[str]:
    """Use LLM to generate personalized summaries for each service result."""
    try:
        client = get_azure_client()

        # Build context
        profile_context = ""
        if research_profile:
            fields = ", ".join(research_profile.get("primary_fields", []))
            topics = ", ".join(research_profile.get("recent_topics", []))
            profile_context = f"Researcher's fields: {fields}. Recent topics: {topics}."

        # Build results summary for the LLM
        results_text = []
        for r in results:
            service = r["service"]
            full = r.get("full_results", {})
            # Truncate full results to avoid token limits
            results_text.append(f"Service: {service}\nResults: {json.dumps(full, default=str)[:3000]}")

        response = client.chat.completions.create(
            model=AZURE_CHAT_DEPLOYMENT,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Generate concise, personalized summaries for research analysis results. "
                        "Each summary should be 2-4 sentences, use markdown formatting, and reference "
                        "the researcher's context when relevant. "
                        "Return a JSON array of strings, one summary per result.\n"
                        f"Researcher context: {profile_context}\n"
                        f"User's question: {user_message}"
                    ),
                },
                {
                    "role": "user",
                    "content": "\n\n---\n\n".join(results_text),
                },
            ],
            temperature=0.5,
            max_tokens=1500,
        )

        raw = response.choices[0].message.content.strip()
        try:
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
            summaries = json.loads(raw)
            if isinstance(summaries, list):
                return [str(s) for s in summaries]
        except json.JSONDecodeError:
            pass

        # Fallback: return the raw text as a single summary
        return [raw] * len(results)

    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        return ["Analysis complete. Click 'View full analysis' for details."] * len(results)


def _generate_followups(
    results: List[Dict],
    research_profile: Optional[Dict],
) -> List[str]:
    """Generate followup action suggestions based on which services ran."""
    ran_services = {r["service"] for r in results if r["status"] == "success"}
    all_services = {"hij", "competitor_finder", "idea_reality", "co_researcher"}
    not_run = all_services - ran_services

    suggestions = []

    if "competitor_finder" in not_run and "hij" in ran_services:
        suggestions.append("Want me to find competitors in this research area?")
    if "idea_reality" in not_run:
        suggestions.append("Should I check if your research idea is novel?")
    if "co_researcher" in not_run:
        suggestions.append("Want me to brainstorm research hypotheses?")
    if "hij" in not_run:
        suggestions.append("Would you like me to score a manuscript?")

    return suggestions[:3]  # Max 3 suggestions
```

- [ ] **Step 2: Commit**

```bash
cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work
git add backend/services/chat_orchestrator/response_merger.py
git commit -m "feat: add response merger with personalized tab summaries"
```

---

## Task 10: Orchestrator Route (API Endpoint)

**Files:**
- Create: `backend/api/orchestrator_routes.py`
- Modify: `backend/app_v2.py:293` (register blueprint)

- [ ] **Step 1: Write the orchestrator route**

Create `backend/api/orchestrator_routes.py`:

```python
"""API route for the Chat Orchestrator — POST /api/chat/orchestrated"""

import os
import json
import uuid
import shutil
import logging
import tempfile
from flask import Blueprint, request, g, Response, stream_with_context
from services.auth_service import require_auth

logger = logging.getLogger(__name__)

orchestrator_bp = Blueprint("orchestrator", __name__, url_prefix="/api/chat")


def _sse_event(event: str, data: dict) -> str:
    """Format an SSE event string."""
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@orchestrator_bp.route("/orchestrated", methods=["POST"])
@require_auth
def orchestrated_chat():
    """
    Main orchestrated chat endpoint. Accepts multipart form data with:
    - message: text message
    - metadata: JSON string with conversation_id, power_hint
    - files: optional file attachments

    Returns SSE stream with orchestrator events.
    """
    tenant_id = g.tenant_id
    user_id = g.user_id

    # Parse request (multipart or JSON)
    if request.content_type and "multipart" in request.content_type:
        message = request.form.get("message", "")
        metadata_str = request.form.get("metadata", "{}")
        try:
            metadata = json.loads(metadata_str)
        except json.JSONDecodeError:
            metadata = {}
        uploaded_files = request.files.getlist("files")
    else:
        data = request.get_json() or {}
        message = data.get("message", "")
        metadata = data
        uploaded_files = []

    power_hint = metadata.get("power_hint")
    conversation_id = metadata.get("conversation_id")

    # Read file bytes if uploaded
    file_bytes = None
    filename = None
    if uploaded_files:
        f = uploaded_files[0]  # Use first file
        file_bytes = f.read()
        filename = f.filename

    def generate():
        try:
            # --- LAYER 1: Intent Gate ---
            yield _sse_event("thinking", {"step": "Analyzing your request..."})

            from services.chat_orchestrator.intent_gate import IntentGate
            gate = IntentGate()
            classification = gate.classify(message, power_hint=power_hint)

            if not classification["needs_powers"]:
                # Not a power request — tell frontend to use standard chat
                yield _sse_event("fallback", {"reason": "standard_chat"})
                yield _sse_event("done", {})
                return

            powers = classification["powers"]
            skip_router = classification["skip_router"]

            # --- CONTEXT INJECTION ---
            yield _sse_event("thinking", {"step": "Loading your research context..."})

            from services.chat_orchestrator.context_injector import inject_context
            context_package = inject_context(tenant_id, message)

            yield _sse_event("context_loaded", {
                "profile_fields": context_package.get("profile_fields", []),
                "chunks_found": context_package.get("chunks_found", 0),
            })

            # --- LAYER 2: Tool Router ---
            if skip_router and len(powers) == 1:
                # Explicit trigger or single clear intent — skip LLM router
                from services.chat_orchestrator.tool_router import extract_params_simple
                args = extract_params_simple(message, powers[0], context_package)
                tool_calls = [{"service": powers[0], "args": args}]
            else:
                yield _sse_event("thinking", {"step": "Determining which tools to use..."})
                from services.chat_orchestrator.tool_router import route
                tool_calls = route(message, context_package)

            if not tool_calls:
                yield _sse_event("fallback", {"reason": "no_tools_selected"})
                yield _sse_event("done", {})
                return

            # Check if HIJ needs a file but none provided
            for tc in tool_calls:
                if tc["service"] == "hij" and not file_bytes:
                    raw_text = tc.get("args", {}).get("paper_text") or message
                    if len(raw_text) < 200:
                        yield _sse_event("file_needed", {
                            "service": "hij",
                            "message": "Please attach your manuscript to score it.",
                        })
                        yield _sse_event("done", {})
                        return

            # --- LAYER 3: Parallel Execution ---
            service_names = [tc["service"] for tc in tool_calls]
            yield _sse_event("services_started", {"services": service_names})

            def on_complete(service, status):
                pass  # Can't yield from callback — handled via results

            from services.chat_orchestrator.parallel_executor import execute
            results = execute(
                tool_calls=tool_calls,
                context_package=context_package,
                file_bytes=file_bytes,
                filename=filename,
                tenant_id=tenant_id,
            )

            # Send completion events for each service
            for result in results:
                yield _sse_event("service_complete", {
                    "service": result["service"],
                    "status": result["status"],
                })

            # --- RESPONSE MERGER ---
            yield _sse_event("thinking", {"step": "Generating your personalized summary..."})

            from services.chat_orchestrator.response_merger import merge
            merged = merge(
                results=results,
                research_profile=context_package.get("research_profile"),
                user_message=message,
            )

            # --- PERSIST TO CONVERSATION ---
            _save_to_conversation(
                tenant_id=tenant_id,
                user_id=user_id,
                conversation_id=conversation_id,
                user_message=message,
                merged_result=merged,
            )

            # --- SEND FINAL RESULT ---
            yield _sse_event("result", merged)
            yield _sse_event("done", {})

        except Exception as e:
            logger.error(f"Orchestrator error: {e}", exc_info=True)
            yield _sse_event("error", {"message": str(e)})
            yield _sse_event("done", {})

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _save_to_conversation(
    tenant_id: str,
    user_id: str,
    conversation_id: str | None,
    user_message: str,
    merged_result: dict,
):
    """Persist the orchestrated exchange to the conversation history."""
    try:
        from database.models import SessionLocal, ChatConversation, ChatMessage
        from database.models import generate_uuid
        from datetime import datetime, timezone

        db = SessionLocal()
        try:
            # Get or create conversation
            if conversation_id:
                conv = db.query(ChatConversation).filter(
                    ChatConversation.id == conversation_id,
                    ChatConversation.tenant_id == tenant_id,
                ).first()
            else:
                conv = None

            if not conv:
                conv = ChatConversation(
                    id=generate_uuid(),
                    tenant_id=tenant_id,
                    user_id=user_id,
                    title=user_message[:100],
                )
                db.add(conv)
                db.flush()

            now = datetime.now(timezone.utc)

            # Save user message
            user_msg = ChatMessage(
                id=generate_uuid(),
                conversation_id=conv.id,
                tenant_id=tenant_id,
                role="user",
                content=user_message,
                message_type="text",
                created_at=now,
            )
            db.add(user_msg)

            # Save assistant response with power result
            # Build a text summary for the content field
            tab_labels = [t["label"] for t in merged_result.get("tabs", [])]
            content_text = f"Power analysis: {', '.join(tab_labels)}"

            assistant_msg = ChatMessage(
                id=generate_uuid(),
                conversation_id=conv.id,
                tenant_id=tenant_id,
                role="assistant",
                content=content_text,
                message_type="power_result",
                extra_data=merged_result,
                created_at=now,
            )
            db.add(assistant_msg)

            conv.last_message_at = now
            db.commit()

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Failed to save orchestrated conversation: {e}", exc_info=True)
```

- [ ] **Step 2: Register the blueprint in app_v2.py**

In `backend/app_v2.py`, add after line 293 (`app.register_blueprint(idea_reality_bp)`):

```python
from api.orchestrator_routes import orchestrator_bp
app.register_blueprint(orchestrator_bp)
```

Also add the import near the top with the other blueprint imports.

- [ ] **Step 3: Verify the app starts**

Run:
```bash
cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work/backend
python -c "from app_v2 import app; print('App loaded with orchestrator blueprint')"
```
Expected: `App loaded with orchestrator blueprint`

- [ ] **Step 4: Commit**

```bash
cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work
git add backend/api/orchestrator_routes.py backend/app_v2.py
git commit -m "feat: add /api/chat/orchestrated SSE endpoint"
```

---

## Task 11: Frontend — Powers Trigger Button

**Files:**
- Create: `frontend/components/co-work/PowersTrigger.tsx`

- [ ] **Step 1: Write the PowersTrigger component**

Create `frontend/components/co-work/PowersTrigger.tsx`:

```tsx
'use client'

import React, { useState, useRef, useEffect } from 'react'

const COLORS = {
  primary: '#C9A598',
  primaryLight: '#FBF4F1',
  cardBg: '#FFFFFF',
  textPrimary: '#2D2D2D',
  textSecondary: '#6B6B6B',
  border: '#F0EEEC',
  amber: '#D4A853',
}
const FONT = "Avenir, 'Avenir Next', 'DM Sans', system-ui, sans-serif"

interface Power {
  id: string
  label: string
  icon: string
  needsFile: boolean
  description: string
}

const POWERS: Power[] = [
  {
    id: 'hij',
    label: 'Score Manuscript',
    icon: '📄',
    needsFile: true,
    description: 'Evaluate your paper and match to journals',
  },
  {
    id: 'competitor_finder',
    label: 'Find Competitors',
    icon: '🔍',
    needsFile: false,
    description: 'Search for competing labs and grants',
  },
  {
    id: 'idea_reality',
    label: 'Validate Idea',
    icon: '💡',
    needsFile: false,
    description: 'Check if your idea is novel',
  },
  {
    id: 'co_researcher',
    label: 'Co-Researcher',
    icon: '🧪',
    needsFile: false,
    description: 'Brainstorm research hypotheses',
  },
]

interface PowersTriggerProps {
  onSelectPower: (powerId: string, file?: File) => void
  disabled?: boolean
}

export default function PowersTrigger({ onSelectPower, disabled }: PowersTriggerProps) {
  const [isOpen, setIsOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [pendingPower, setPendingPower] = useState<string | null>(null)

  // Close menu on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setIsOpen(false)
      }
    }
    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [isOpen])

  const handlePowerClick = (power: Power) => {
    if (power.needsFile) {
      setPendingPower(power.id)
      fileInputRef.current?.click()
    } else {
      onSelectPower(power.id)
      setIsOpen(false)
    }
  }

  const handleFileSelected = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file && pendingPower) {
      onSelectPower(pendingPower, file)
      setPendingPower(null)
      setIsOpen(false)
    }
    // Reset input
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  return (
    <div ref={menuRef} style={{ position: 'relative' }}>
      {/* Trigger button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        disabled={disabled}
        title="Research Powers"
        style={{
          width: '36px',
          height: '36px',
          borderRadius: '8px',
          border: `1px solid ${COLORS.border}`,
          backgroundColor: isOpen ? COLORS.primaryLight : 'transparent',
          cursor: disabled ? 'not-allowed' : 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          opacity: disabled ? 0.5 : 1,
          transition: 'all 0.15s ease',
          flexShrink: 0,
        }}
        onMouseEnter={(e) => {
          if (!disabled) (e.target as HTMLElement).style.backgroundColor = COLORS.primaryLight
        }}
        onMouseLeave={(e) => {
          if (!disabled && !isOpen) (e.target as HTMLElement).style.backgroundColor = 'transparent'
        }}
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={COLORS.primary} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
        </svg>
      </button>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.doc,.docx,.txt"
        onChange={handleFileSelected}
        style={{ display: 'none' }}
      />

      {/* Popover menu */}
      {isOpen && (
        <div style={{
          position: 'absolute',
          bottom: '44px',
          right: '0',
          width: '260px',
          backgroundColor: COLORS.cardBg,
          borderRadius: '12px',
          border: `1px solid ${COLORS.border}`,
          boxShadow: '0 4px 20px rgba(0,0,0,0.08)',
          padding: '6px',
          zIndex: 100,
          fontFamily: FONT,
        }}>
          <div style={{
            padding: '8px 12px 4px',
            fontSize: '11px',
            fontWeight: 600,
            color: COLORS.textSecondary,
            textTransform: 'uppercase',
            letterSpacing: '0.5px',
          }}>
            Research Powers
          </div>

          {POWERS.map((power) => (
            <button
              key={power.id}
              onClick={() => handlePowerClick(power)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                width: '100%',
                padding: '10px 12px',
                border: 'none',
                backgroundColor: 'transparent',
                borderRadius: '8px',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'background-color 0.1s ease',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = COLORS.primaryLight)}
              onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
            >
              <span style={{ fontSize: '18px', flexShrink: 0 }}>{power.icon}</span>
              <div>
                <div style={{
                  fontSize: '13px',
                  fontWeight: 500,
                  color: COLORS.textPrimary,
                  fontFamily: FONT,
                }}>
                  {power.label}
                </div>
                <div style={{
                  fontSize: '11px',
                  color: COLORS.textSecondary,
                  fontFamily: FONT,
                  marginTop: '1px',
                }}>
                  {power.description}
                </div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work
git add frontend/components/co-work/PowersTrigger.tsx
git commit -m "feat: add PowersTrigger button component with popover menu"
```

---

## Task 12: Frontend — Power Result Card + Loading Card

**Files:**
- Create: `frontend/components/co-work/PowerResultCard.tsx`
- Create: `frontend/components/co-work/PowerLoadingCard.tsx`

- [ ] **Step 1: Write PowerResultCard**

Create `frontend/components/co-work/PowerResultCard.tsx`:

```tsx
'use client'

import React, { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const COLORS = {
  primary: '#C9A598',
  primaryLight: '#FBF4F1',
  cardBg: '#FFFFFF',
  textPrimary: '#2D2D2D',
  textSecondary: '#6B6B6B',
  textMuted: '#9A9A9A',
  border: '#F0EEEC',
  success: '#9CB896',
  error: '#D97B7B',
  amber: '#D4A853',
}
const FONT = "Avenir, 'Avenir Next', 'DM Sans', system-ui, sans-serif"

interface Tab {
  label: string
  icon: string
  status: 'success' | 'error' | 'timeout'
  summary: string
  full_results: any | null
}

interface PowerResultCardProps {
  tabs: Tab[]
  followup_suggestions: string[]
  onViewFullAnalysis?: (tab: Tab) => void
  onFollowupClick?: (suggestion: string) => void
}

export default function PowerResultCard({
  tabs,
  followup_suggestions,
  onViewFullAnalysis,
  onFollowupClick,
}: PowerResultCardProps) {
  const [activeTab, setActiveTab] = useState(0)

  if (!tabs || tabs.length === 0) return null

  const currentTab = tabs[activeTab]
  const isError = currentTab.status === 'error' || currentTab.status === 'timeout'

  return (
    <div style={{
      backgroundColor: COLORS.cardBg,
      borderRadius: '14px',
      border: `1px solid ${COLORS.border}`,
      overflow: 'hidden',
      fontFamily: FONT,
      maxWidth: '100%',
    }}>
      {/* Tab bar */}
      <div style={{
        display: 'flex',
        borderBottom: `1px solid ${COLORS.border}`,
        backgroundColor: '#FAFAF9',
      }}>
        {tabs.map((tab, idx) => (
          <button
            key={idx}
            onClick={() => setActiveTab(idx)}
            style={{
              flex: 1,
              padding: '10px 16px',
              border: 'none',
              backgroundColor: idx === activeTab ? COLORS.cardBg : 'transparent',
              borderBottom: idx === activeTab ? `2px solid ${COLORS.primary}` : '2px solid transparent',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              fontSize: '12px',
              fontWeight: idx === activeTab ? 600 : 400,
              color: idx === activeTab ? COLORS.textPrimary : COLORS.textSecondary,
              fontFamily: FONT,
              transition: 'all 0.15s ease',
            }}
          >
            {tab.status === 'error' || tab.status === 'timeout' ? (
              <span style={{ color: COLORS.error }}>⚠</span>
            ) : null}
            <span>{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div style={{
        padding: '16px 20px',
        fontSize: '14px',
        lineHeight: '1.6',
        color: isError ? COLORS.error : COLORS.textPrimary,
        minHeight: '80px',
      }}>
        {isError ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span>⚠️</span>
            <span>{currentTab.summary}</span>
          </div>
        ) : (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {currentTab.summary || 'Analysis complete.'}
          </ReactMarkdown>
        )}
      </div>

      {/* View full analysis button */}
      {currentTab.status === 'success' && currentTab.full_results && onViewFullAnalysis && (
        <div style={{ padding: '0 20px 12px' }}>
          <button
            onClick={() => onViewFullAnalysis(currentTab)}
            style={{
              padding: '8px 16px',
              borderRadius: '8px',
              border: `1px solid ${COLORS.primary}`,
              backgroundColor: 'transparent',
              color: COLORS.primary,
              fontSize: '12px',
              fontWeight: 500,
              cursor: 'pointer',
              fontFamily: FONT,
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.backgroundColor = COLORS.primaryLight
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.backgroundColor = 'transparent'
            }}
          >
            View full analysis →
          </button>
        </div>
      )}

      {/* Followup suggestions */}
      {followup_suggestions && followup_suggestions.length > 0 && (
        <div style={{
          padding: '10px 20px 14px',
          borderTop: `1px solid ${COLORS.border}`,
          display: 'flex',
          flexWrap: 'wrap',
          gap: '6px',
        }}>
          {followup_suggestions.map((suggestion, idx) => (
            <button
              key={idx}
              onClick={() => onFollowupClick?.(suggestion)}
              style={{
                padding: '5px 12px',
                borderRadius: '20px',
                border: `1px solid ${COLORS.border}`,
                backgroundColor: COLORS.cardBg,
                color: COLORS.textSecondary,
                fontSize: '11px',
                cursor: 'pointer',
                fontFamily: FONT,
                transition: 'all 0.15s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = COLORS.primary
                e.currentTarget.style.color = COLORS.primary
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = COLORS.border
                e.currentTarget.style.color = COLORS.textSecondary
              }}
            >
              {suggestion}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Write PowerLoadingCard**

Create `frontend/components/co-work/PowerLoadingCard.tsx`:

```tsx
'use client'

import React from 'react'

const COLORS = {
  primary: '#C9A598',
  cardBg: '#FFFFFF',
  textPrimary: '#2D2D2D',
  textSecondary: '#6B6B6B',
  border: '#F0EEEC',
  success: '#9CB896',
}
const FONT = "Avenir, 'Avenir Next', 'DM Sans', system-ui, sans-serif"

const SERVICE_LABELS: Record<string, string> = {
  hij: 'Scoring manuscript',
  competitor_finder: 'Finding competitors',
  idea_reality: 'Validating idea',
  co_researcher: 'Generating hypotheses',
}

interface PowerLoadingCardProps {
  services: string[]
  completedServices: Record<string, string>  // service -> status
  thinkingStep?: string
}

export default function PowerLoadingCard({
  services,
  completedServices,
  thinkingStep,
}: PowerLoadingCardProps) {
  return (
    <div style={{
      backgroundColor: COLORS.cardBg,
      borderRadius: '14px',
      border: `1px solid ${COLORS.border}`,
      padding: '16px 20px',
      fontFamily: FONT,
      maxWidth: '100%',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '8px',
        marginBottom: '14px',
      }}>
        <div className="power-loading-spinner" style={{
          width: '16px',
          height: '16px',
          border: `2px solid ${COLORS.border}`,
          borderTopColor: COLORS.primary,
          borderRadius: '50%',
        }} />
        <span style={{
          fontSize: '13px',
          fontWeight: 500,
          color: COLORS.textPrimary,
        }}>
          Running analysis...
        </span>
      </div>

      {/* Service list */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        {services.map((service) => {
          const completed = service in completedServices
          const status = completedServices[service]
          const isError = status === 'error' || status === 'timeout'

          return (
            <div key={service} style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '13px',
              color: completed
                ? (isError ? '#D97B7B' : COLORS.success)
                : COLORS.textSecondary,
            }}>
              {completed ? (
                isError ? (
                  <span style={{ fontSize: '14px' }}>✗</span>
                ) : (
                  <span style={{ fontSize: '14px' }}>✓</span>
                )
              ) : (
                <div className="power-loading-dot" style={{
                  width: '6px',
                  height: '6px',
                  borderRadius: '50%',
                  backgroundColor: COLORS.primary,
                }} />
              )}
              <span>{SERVICE_LABELS[service] || service}...</span>
            </div>
          )
        })}
      </div>

      {/* Thinking step */}
      {thinkingStep && (
        <div style={{
          marginTop: '12px',
          fontSize: '12px',
          color: COLORS.textSecondary,
          fontStyle: 'italic',
        }}>
          {thinkingStep}
        </div>
      )}

      <style>{`
        @keyframes power-spin {
          to { transform: rotate(360deg); }
        }
        .power-loading-spinner {
          animation: power-spin 0.8s linear infinite;
        }
        @keyframes power-pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
        .power-loading-dot {
          animation: power-pulse 1.5s ease-in-out infinite;
        }
      `}</style>
    </div>
  )
}
```

- [ ] **Step 3: Commit**

```bash
cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work
git add frontend/components/co-work/PowerResultCard.tsx frontend/components/co-work/PowerLoadingCard.tsx
git commit -m "feat: add PowerResultCard and PowerLoadingCard frontend components"
```

---

## Task 13: Frontend — Integrate into CoWorkChat

**Files:**
- Modify: `frontend/components/co-work/CoWorkChat.tsx`

This is the most critical integration task. We need to:
1. Import PowersTrigger, PowerResultCard, PowerLoadingCard
2. Add power state variables
3. Add the PowersTrigger button to the input bar (next to send arrow)
4. Add orchestrated SSE handler
5. Render PowerResultCard and PowerLoadingCard in message list

- [ ] **Step 1: Add imports at top of CoWorkChat.tsx (after line 5)**

Add after the existing imports:

```tsx
import PowersTrigger from './PowersTrigger'
import PowerResultCard from './PowerResultCard'
import PowerLoadingCard from './PowerLoadingCard'
```

- [ ] **Step 2: Add power state variables (after line 103)**

Add after the existing state variables:

```tsx
  // Power orchestrator state
  const [activePowerHint, setActivePowerHint] = useState<string | null>(null)
  const [powerFile, setPowerFile] = useState<File | null>(null)
  const [isPowerLoading, setIsPowerLoading] = useState(false)
  const [powerServices, setPowerServices] = useState<string[]>([])
  const [powerCompletedServices, setPowerCompletedServices] = useState<Record<string, string>>({})
  const [powerThinkingStep, setPowerThinkingStep] = useState<string>('')
```

- [ ] **Step 3: Add the orchestrated send handler**

Add a new function `handlePowerSend` near the existing `handleSend` function. This handles the SSE stream from `/api/chat/orchestrated`:

```tsx
  const handlePowerSend = async (message: string, powerHint: string | null, file: File | null) => {
    if (!message.trim() && !file) return

    // Add user message to chat
    const userMsg: Message = {
      id: Date.now().toString(),
      text: message,
      isUser: true,
      timestamp: new Date(),
    }
    setMessages(prev => [...prev, userMsg])
    setInputValue('')
    setIsPowerLoading(true)
    setPowerServices([])
    setPowerCompletedServices({})
    setPowerThinkingStep('Analyzing your request...')

    try {
      const formData = new FormData()
      formData.append('message', message)
      formData.append('metadata', JSON.stringify({
        conversation_id: conversationId,
        power_hint: powerHint,
      }))
      if (file) {
        formData.append('files', file)
      }

      const response = await fetch(`${apiBase}/chat/orchestrated`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        body: formData,
      })

      if (!response.ok) throw new Error(`HTTP ${response.status}`)

      const reader = response.body!.getReader()
      const decoder = new TextDecoder()
      let sseBuffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        sseBuffer += decoder.decode(value, { stream: true })
        const events = sseBuffer.split('\n\n')
        sseBuffer = events.pop() || ''

        for (const eventStr of events) {
          if (!eventStr.trim()) continue

          let eventType = 'message'
          let eventData: any = {}

          for (const line of eventStr.split('\n')) {
            if (line.startsWith('event:')) eventType = line.slice(6).trim()
            else if (line.startsWith('data:')) {
              try {
                eventData = JSON.parse(line.slice(5).trim())
              } catch { eventData = line.slice(5).trim() }
            }
          }

          switch (eventType) {
            case 'thinking':
              setPowerThinkingStep(eventData.step || '')
              break

            case 'fallback':
              // Not a power request — fall back to standard chat
              setIsPowerLoading(false)
              setPowerFile(null)
              setActivePowerHint(null)
              // Remove the user message we added and re-send via standard path
              setMessages(prev => prev.filter(m => m.id !== userMsg.id))
              setInputValue(message)
              // Use setTimeout to let state update before calling handleSend
              setTimeout(() => handleSend(), 0)
              return

            case 'context_loaded':
              setPowerThinkingStep(
                `Context loaded: ${eventData.chunks_found} relevant documents found`
              )
              break

            case 'services_started':
              setPowerServices(eventData.services || [])
              break

            case 'service_complete':
              setPowerCompletedServices(prev => ({
                ...prev,
                [eventData.service]: eventData.status,
              }))
              break

            case 'file_needed':
              // Service needs a file — show message
              const fileMsg: Message = {
                id: Date.now().toString(),
                text: eventData.message || 'Please attach a file to continue.',
                isUser: false,
                timestamp: new Date(),
              }
              setMessages(prev => [...prev, fileMsg])
              setIsPowerLoading(false)
              return

            case 'result':
              // Final tabbed result
              const resultMsg: Message = {
                id: Date.now().toString(),
                text: '',
                isUser: false,
                timestamp: new Date(),
                powerResult: eventData,
              }
              setMessages(prev => [...prev, resultMsg])
              break

            case 'error':
              const errorMsg: Message = {
                id: Date.now().toString(),
                text: `Error: ${eventData.message || 'Something went wrong'}`,
                isUser: false,
                timestamp: new Date(),
              }
              setMessages(prev => [...prev, errorMsg])
              break

            case 'done':
              break
          }
        }
      }
    } catch (err: any) {
      const errorMsg: Message = {
        id: Date.now().toString(),
        text: `Error: ${err.message || 'Connection failed'}`,
        isUser: false,
        timestamp: new Date(),
      }
      setMessages(prev => [...prev, errorMsg])
    } finally {
      setIsPowerLoading(false)
      setPowerFile(null)
      setActivePowerHint(null)
      setPowerServices([])
      setPowerCompletedServices({})
      setPowerThinkingStep('')
    }
  }
```

- [ ] **Step 4: Update the Message interface**

Find the `Message` interface (near the top of the file) and add the `powerResult` field:

```tsx
interface Message {
  id: string
  text: string
  isUser: boolean
  timestamp: Date
  sources?: any[]
  attachments?: any[]
  confidence?: number
  powerResult?: any  // Add this line
}
```

- [ ] **Step 5: Modify handleSend to detect powers**

At the beginning of the existing `handleSend` function, add power detection. If a power_hint is active or the intent gate detects powers, route to `handlePowerSend`:

```tsx
  // Add at the start of handleSend, before the existing logic:
  if (activePowerHint || powerFile) {
    handlePowerSend(inputValue, activePowerHint, powerFile)
    return
  }
  // Note: handleSend takes no args. The fallback path in handlePowerSend
  // sets inputValue back and calls handleSend() with no args.
```

- [ ] **Step 6: Add PowersTrigger to the input bar**

In the input bar area (~line 1058), add the PowersTrigger button between the textarea and the send button:

```tsx
    {/* PowersTrigger button — add between textarea and send button */}
    <PowersTrigger
      onSelectPower={(powerId: string, file?: File) => {
        setActivePowerHint(powerId)
        if (file) setPowerFile(file)
      }}
      disabled={isLoading || isStreaming || isPowerLoading}
    />
```

- [ ] **Step 7: Add power result rendering in the message list**

In the message rendering section (~line 761), add PowerResultCard rendering. Inside the message map, after the regular message rendering, add:

```tsx
    {/* Power result card */}
    {message.powerResult && (
      <PowerResultCard
        tabs={message.powerResult.tabs || []}
        followup_suggestions={message.powerResult.followup_suggestions || []}
        onFollowupClick={(suggestion) => {
          setInputValue(suggestion)
        }}
      />
    )}
```

- [ ] **Step 8: Add PowerLoadingCard rendering**

After the messages list and before the input area, add the loading card when powers are running:

```tsx
    {/* Power loading state */}
    {isPowerLoading && powerServices.length > 0 && (
      <div style={{ padding: '0 16px 12px' }}>
        <PowerLoadingCard
          services={powerServices}
          completedServices={powerCompletedServices}
          thinkingStep={powerThinkingStep}
        />
      </div>
    )}
```

- [ ] **Step 9: Add active power indicator above input**

When a power is selected (via the trigger menu), show a small indicator above the input bar:

```tsx
    {/* Active power indicator */}
    {activePowerHint && (
      <div style={{
        padding: '6px 16px',
        display: 'flex',
        alignItems: 'center',
        gap: '6px',
        fontSize: '12px',
        color: COLORS.primary,
        fontFamily: FONT,
      }}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
        </svg>
        <span>
          {activePowerHint === 'hij' ? 'Score Manuscript' :
           activePowerHint === 'competitor_finder' ? 'Find Competitors' :
           activePowerHint === 'idea_reality' ? 'Validate Idea' :
           'Co-Researcher'} mode active
        </span>
        {powerFile && <span style={{ color: COLORS.textSecondary }}>• {powerFile.name}</span>}
        <button
          onClick={() => { setActivePowerHint(null); setPowerFile(null) }}
          style={{
            border: 'none',
            background: 'none',
            cursor: 'pointer',
            color: COLORS.textSecondary,
            fontSize: '14px',
            padding: '0 4px',
          }}
        >
          ✕
        </button>
      </div>
    )}
```

- [ ] **Step 10: Commit**

```bash
cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work
git add frontend/components/co-work/CoWorkChat.tsx
git commit -m "feat: integrate powers trigger, result cards, and orchestrated SSE into CoWorkChat"
```

---

## Task 14: FullAnalysisPanel + Conversation Reload Fixes

**Files:**
- Create: `frontend/components/co-work/FullAnalysisPanel.tsx`
- Modify: `backend/database/models.py` (ChatMessage.to_dict)
- Modify: `frontend/components/co-work/CoWorkChat.tsx` (loadConversation)

- [ ] **Step 1: Create FullAnalysisPanel component**

Create `frontend/components/co-work/FullAnalysisPanel.tsx`:

```tsx
'use client'

import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const COLORS = {
  primary: '#C9A598',
  primaryLight: '#FBF4F1',
  cardBg: '#FFFFFF',
  textPrimary: '#2D2D2D',
  textSecondary: '#6B6B6B',
  textMuted: '#9A9A9A',
  border: '#F0EEEC',
  success: '#9CB896',
}
const FONT = "Avenir, 'Avenir Next', 'DM Sans', system-ui, sans-serif"

interface FullAnalysisPanelProps {
  label: string
  fullResults: any
  onClose: () => void
}

export default function FullAnalysisPanel({ label, fullResults, onClose }: FullAnalysisPanelProps) {
  if (!fullResults) return null

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      backgroundColor: COLORS.cardBg,
      fontFamily: FONT,
    }}>
      {/* Header */}
      <div style={{
        padding: '14px 20px',
        borderBottom: `1px solid ${COLORS.border}`,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={COLORS.primary} strokeWidth="2">
            <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
          </svg>
          <span style={{ fontSize: '14px', fontWeight: 600, color: COLORS.textPrimary }}>
            {label} — Full Analysis
          </span>
        </div>
        <button
          onClick={onClose}
          style={{
            border: 'none',
            background: 'none',
            cursor: 'pointer',
            color: COLORS.textSecondary,
            fontSize: '18px',
            padding: '4px',
          }}
        >
          ✕
        </button>
      </div>

      {/* Results body */}
      <div style={{
        flex: 1,
        overflow: 'auto',
        padding: '16px 20px',
      }}>
        {renderResults(label, fullResults)}
      </div>
    </div>
  )
}

function renderResults(label: string, results: any): React.ReactNode {
  if (!results) return <p style={{ color: '#9A9A9A' }}>No detailed results available.</p>

  // Render as formatted JSON sections
  return (
    <div style={{ fontSize: '13px', lineHeight: '1.7', color: '#2D2D2D' }}>
      {Object.entries(results).map(([key, value]) => {
        if (key === 'raw_events') return null // Skip raw events

        return (
          <div key={key} style={{ marginBottom: '16px' }}>
            <div style={{
              fontSize: '12px',
              fontWeight: 600,
              color: '#6B6B6B',
              textTransform: 'uppercase',
              letterSpacing: '0.5px',
              marginBottom: '6px',
            }}>
              {key.replace(/_/g, ' ')}
            </div>
            <div style={{
              padding: '12px',
              backgroundColor: '#FAFAF9',
              borderRadius: '8px',
              border: '1px solid #F0EEEC',
            }}>
              {typeof value === 'string' ? (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{value}</ReactMarkdown>
              ) : Array.isArray(value) ? (
                <ul style={{ margin: 0, paddingLeft: '16px' }}>
                  {value.map((item, i) => (
                    <li key={i} style={{ marginBottom: '4px' }}>
                      {typeof item === 'object' ? (
                        <pre style={{ margin: 0, fontSize: '12px', whiteSpace: 'pre-wrap' }}>
                          {JSON.stringify(item, null, 2)}
                        </pre>
                      ) : String(item)}
                    </li>
                  ))}
                </ul>
              ) : typeof value === 'object' && value !== null ? (
                <pre style={{ margin: 0, fontSize: '12px', whiteSpace: 'pre-wrap' }}>
                  {JSON.stringify(value, null, 2)}
                </pre>
              ) : (
                <span>{String(value)}</span>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 2: Add message_type to ChatMessage.to_dict()**

In `backend/database/models.py`, find the ChatMessage `to_dict` method and add `message_type`:

```python
    def to_dict(self):
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "message_type": self.message_type or "text",  # Add this line
            "sources": self.sources or [],
            "extra_data": self.extra_data or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
```

- [ ] **Step 3: Fix loadConversation in CoWorkChat.tsx to restore power results**

In the `loadConversation` function in `CoWorkChat.tsx`, update the message mapping to check for `message_type`:

```tsx
  // In the loadConversation function, update the message mapping:
  const loaded: Message[] = data.conversation.messages.map((m: any) => ({
    id: m.id,
    text: m.content,
    isUser: m.role === 'user',
    sources: m.sources || [],
    // Restore power results from extra_data
    powerResult: m.message_type === 'power_result' ? m.extra_data : undefined,
  }))
```

- [ ] **Step 4: Wire up FullAnalysisPanel in CoWorkChat.tsx**

Add state for the full analysis panel and render it. Add state variable:

```tsx
  const [fullAnalysis, setFullAnalysis] = useState<{label: string, fullResults: any} | null>(null)
```

Import the component:

```tsx
import FullAnalysisPanel from './FullAnalysisPanel'
```

Update PowerResultCard to pass the handler:

```tsx
    <PowerResultCard
      tabs={message.powerResult.tabs || []}
      followup_suggestions={message.powerResult.followup_suggestions || []}
      onViewFullAnalysis={(tab) => setFullAnalysis({ label: tab.label, fullResults: tab.full_results })}
      onFollowupClick={(suggestion) => setInputValue(suggestion)}
    />
```

In the right panel area, conditionally render FullAnalysisPanel when active (this depends on how the parent page manages the right panel — the panel content may need to be passed up via a callback prop or rendered conditionally alongside CoWorkContext).

- [ ] **Step 5: Commit**

```bash
cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work
git add frontend/components/co-work/FullAnalysisPanel.tsx backend/database/models.py frontend/components/co-work/CoWorkChat.tsx
git commit -m "feat: add FullAnalysisPanel, fix conversation reload for power results, expose message_type"
```

---

## Task 15: End-to-End Smoke Test


- [ ] **Step 1: Verify backend starts**

```bash
cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work/backend
python -c "
from app_v2 import app
with app.test_client() as c:
    # Check the orchestrated endpoint is registered
    rules = [r.rule for r in app.url_map.iter_rules()]
    assert '/api/chat/orchestrated' in rules, f'Endpoint not found. Rules: {rules}'
    print('✓ /api/chat/orchestrated endpoint registered')
    print(f'✓ Total routes: {len(rules)}')
"
```
Expected: Endpoint registered, no import errors

- [ ] **Step 2: Verify frontend builds**

```bash
cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work/frontend
npx next build 2>&1 | tail -20
```
Expected: Build succeeds with no TypeScript errors

- [ ] **Step 3: Verify standalone pages still work**

```bash
cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work/backend
python -c "
from app_v2 import app
with app.test_client() as c:
    rules = [r.rule for r in app.url_map.iter_rules()]
    assert '/api/journal/analyze' in rules, 'HIJ standalone route missing'
    assert '/api/competitor-finder/search' in rules or any('competitor' in r for r in rules), 'Competitor route missing'
    print('✓ Standalone routes intact')
"
```
Expected: All standalone routes still registered

- [ ] **Step 4: Run intent gate tests**

```bash
cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work/backend
python -m pytest tests/test_intent_gate.py -v
```
Expected: All tests pass

- [ ] **Step 5: Commit final state**

```bash
cd /Users/pranavreddymogathala/2ndBRAINPRANAV-work
git add -A
git status
git commit -m "feat: complete chat orchestrator integration — powers in Co-Work chatbot"
```
