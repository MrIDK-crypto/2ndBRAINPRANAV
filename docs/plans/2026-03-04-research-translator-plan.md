# Research Translator Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rebuild the Co-Researcher tool as a cross-domain Research Translator that decomposes papers into abstraction layers, attempts translations, adversarially stress-tests them, and supports interactive refinement.

**Architecture:** Flask backend with SSE streaming, 4 pipeline phases (parse→decompose→translate→stress-test) + interactive chat. Next.js frontend with warm cream design system.

**Tech Stack:** Flask, Azure OpenAI (GPT-5), LlamaParse, python-docx, Next.js 14, React 18, TypeScript

**Design doc:** `docs/plans/2026-03-04-research-translator-design.md`

---

### Task 1: Parser — Add DOCX Support

**Files:**
- Modify: `backend/co_researcher/parser.py`

**What to do:**

Update `parser.py` to handle both PDF and DOCX files. Add a `parse_document()` dispatcher that checks the file extension and routes to LlamaParse (PDF) or python-docx (DOCX).

```python
def parse_document(file_bytes: bytes, filename: str) -> str:
    """Parse PDF or DOCX. Returns extracted text as markdown."""
    ext = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''
    if ext == 'pdf':
        return parse_pdf(file_bytes, filename)
    elif ext in ('docx', 'doc'):
        return parse_docx(file_bytes, filename)
    else:
        raise ValueError(f"Unsupported file type: .{ext}. Upload PDF or DOCX.")

def parse_docx(file_bytes: bytes, filename: str) -> str:
    """Parse DOCX using python-docx. Returns text content."""
    from docx import Document
    import io
    doc = Document(io.BytesIO(file_bytes))
    paragraphs = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            # Preserve heading structure as markdown
            if para.style and para.style.name.startswith('Heading'):
                level = para.style.name.replace('Heading ', '')
                try:
                    level = int(level)
                except ValueError:
                    level = 2
                paragraphs.append(f"{'#' * level} {text}")
            else:
                paragraphs.append(text)
    return '\n\n'.join(paragraphs)
```

Keep existing `parse_pdf()` unchanged.

**Test:** Parse a DOCX file and verify headings come through as markdown.

**Commit:** `feat: add DOCX support to co-researcher parser`

---

### Task 2: Decomposer — Context Extraction + Layer Decomposition

**Files:**
- Create: `backend/co_researcher/decomposer.py`

**What to do:**

Two main functions:

**`extract_context(text, role)`** — Extracts structured context from a paper. `role` is either `"source"` (paper they read) or `"target"` (their research).

For source papers, extract:
- domain, key_methods (name, what_it_does, why_it_matters, specific_implementation), key_findings, analytical_approaches, conceptual_principles

For target papers, extract:
- domain, experimental_systems, available_techniques, key_regulatory_circuits, open_questions, limitations_acknowledged

**`decompose_layers(source_context, method_or_finding)`** — For a single method/finding from the source paper, decompose into 4 abstraction layers (L4 Principle → L3 Analytical Logic → L2 Design Pattern → L1 Implementation).

```python
def extract_context(text: str, role: str) -> dict:
    """Extract structured context from a paper.
    role: 'source' (paper they read) or 'target' (their research)
    """
    client = get_azure_client()

    if role == "source":
        schema_instruction = """Extract:
- "domain": string (field of research, 1 sentence)
- "key_methods": array of {"name", "what_it_does", "why_it_matters", "specific_implementation"}
- "key_findings": array of {"finding", "evidence_type", "supporting_data"}
- "analytical_approaches": array of strings
- "conceptual_principles": array of strings (field-agnostic insights that could transfer to ANY domain)"""
    else:
        schema_instruction = """Extract:
- "domain": string (field of research, 1 sentence)
- "experimental_systems": array of strings (cell lines, model organisms, etc.)
- "available_techniques": array of strings (methods they clearly use or have access to)
- "key_circuits_or_mechanisms": array of {"name", "description", "components"}
- "open_questions": array of strings (explicit or implied)
- "limitations_acknowledged": array of strings"""

    response = client.chat.completions.create(
        model=AZURE_CHAT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": f"""You are extracting structured research context from a paper for cross-domain translation.

Role of this paper: {"SOURCE — the paper the researcher wants to learn from" if role == "source" else "TARGET — the researcher's own work"}

{schema_instruction}

{"For conceptual_principles: extract the DEEPEST, most field-agnostic version of each insight. Not 'Hox genes modulate digit patterning' but 'A self-organizing system can be characterized by smoothly tuning its control parameters.' The principle should make sense to someone in ANY field." if role == "source" else "For available_techniques: infer from the methods section what this lab can actually do. If they use CRISPR, they can do CRISPR. If they do Western blots, they have protein quantification."}

Output ONLY valid JSON."""},
            {"role": "user", "content": f"{text[:40000]}"},
        ],
        temperature=0.2,
        max_tokens=2000,
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


def decompose_layers(source_context: dict, method_or_finding: dict) -> dict:
    """Decompose a single method/finding into 4 abstraction layers."""
    client = get_azure_client()

    response = client.chat.completions.create(
        model=AZURE_CHAT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": """Decompose this research method/finding into 4 abstraction layers, from most abstract to most concrete.

Each layer must be GENUINELY different from the others — not just rephrasing.

Output JSON:
{
  "layers": [
    {"level": "L4", "name": "Conceptual Principle", "content": "..."},
    {"level": "L3", "name": "Analytical Logic", "content": "..."},
    {"level": "L2", "name": "Design Pattern", "content": "..."},
    {"level": "L1", "name": "Specific Implementation", "content": "..."}
  ]
}

L4 should make sense to someone in ANY scientific field.
L3 should make sense to any experimentalist.
L2 should make sense to someone in the same broad area (e.g., biology).
L1 is specific to THIS paper's exact system."""},
            {"role": "user", "content": f"""Paper domain: {source_context.get('domain', 'Unknown')}

Method/Finding: {json.dumps(method_or_finding)}

Decompose into 4 layers."""},
        ],
        temperature=0.3,
        max_tokens=800,
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)
```

**Commit:** `feat: add decomposer for context extraction and layer decomposition`

---

### Task 3: Translator — Cross-Domain Translation Attempts

**Files:**
- Create: `backend/co_researcher/translator.py`

**What to do:**

**`translate_insight(source_context, target_context, layers)`** — Takes a decomposed insight (4 layers) and attempts to re-instantiate each layer in the target domain.

For each layer (L4→L1), produce:
- `source`: what the source paper does at this level
- `target`: proposed equivalent in the target domain
- `confidence`: 0-1
- `assumption`: what must be true for this mapping to work
- `breaks_if`: condition that would invalidate the mapping

Also identify:
- `overall_break_point`: weakest layer
- `what_to_test_first`: the single experiment that would resolve the biggest uncertainty

```python
def translate_insight(source_context: dict, target_context: dict, layers: dict) -> dict:
    """Attempt cross-domain translation of a decomposed insight."""
    client = get_azure_client()

    response = client.chat.completions.create(
        model=AZURE_CHAT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": """You are performing cross-domain methodological translation.

Given a decomposed research insight (4 layers from a source paper) and context about a target research domain, re-instantiate each layer in the target domain.

CRITICAL: Be honest about where the mapping breaks. A translation that acknowledges its weak points is infinitely more useful than one that pretends everything maps perfectly.

For each layer, output:
- "source": what the source paper does (copy from input)
- "target": proposed equivalent in the target domain
- "confidence": 0.0-1.0
- "assumption": what must be true for this mapping to work
- "breaks_if": specific condition that would invalidate this mapping

Also output:
- "overall_break_point": which layer (L1-L4) is weakest and why
- "what_to_test_first": the single experiment that resolves the biggest uncertainty
- "title": 1-sentence name for this translation proposal

Output ONLY valid JSON."""},
            {"role": "user", "content": f"""## Source Paper Context
{json.dumps(source_context, indent=2)[:8000]}

## Target Paper Context
{json.dumps(target_context, indent=2)[:8000]}

## Decomposed Insight (4 layers)
{json.dumps(layers, indent=2)}

Translate each layer into the target domain. Be explicit about where it breaks."""},
        ],
        temperature=0.4,
        max_tokens=1500,
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)
```

**Commit:** `feat: add translator for cross-domain translation attempts`

---

### Task 4: Adversarial Agents — Stress-Testing Translations

**Files:**
- Create: `backend/co_researcher/adversarial.py`

**What to do:**

4 adversarial agents that attack translations in parallel. Each returns a verdict (`survives`, `vulnerable`, `fatal`), an attack explanation, and what would change their mind.

```python
ADVERSARIAL_AGENTS = [
    {
        "id": "skeptic",
        "name": "Skeptic",
        "color": "#EF4444",
        "role": "Break the translation",
        "prompt": """You are a harsh scientific critic. Your job is to BREAK this translation proposal.

Look for:
- Assumptions that probably don't hold in the target domain
- Forced analogies where the mapping is superficial
- Cases where the principle transfers but the implementation can't
- Biochemical/physical/practical reasons the L2 or L1 mapping would fail

Output JSON:
- "verdict": "survives" | "vulnerable" | "fatal"
- "attack": string (your specific critique, 2-3 sentences)
- "weakest_layer": "L1" | "L2" | "L3" | "L4"
- "what_would_change_my_mind": string (what evidence would make you reconsider)"""
    },
    {
        "id": "prior_art",
        "name": "Prior Art",
        "color": "#3B82F6",
        "role": "Check novelty and precedent",
        "prompt": """You are a literature expert. Check if this cross-domain translation has been attempted before.

Consider:
- Has anyone applied this source methodology to the target field?
- Are there bridge papers connecting these two domains?
- If similar work exists, did it succeed or fail? Why?
- If no precedent exists, is that because no one thought of it, or because it doesn't work?

Output JSON:
- "verdict": "survives" | "vulnerable" | "fatal"
- "attack": string (what you found or didn't find, 2-3 sentences)
- "precedent_exists": boolean
- "bridge_papers_hint": string (describe what to search for, or known examples)
- "what_would_change_my_mind": string"""
    },
    {
        "id": "feasibility",
        "name": "Feasibility",
        "color": "#10B981",
        "role": "Check practical constraints",
        "prompt": """You are a practical experimentalist. Evaluate whether this translation can actually be DONE.

Consider:
- Do the required reagents, constructs, or cell lines exist?
- Does the target lab have the techniques (based on their paper's methods)?
- What's the experimental bottleneck (time, cost, technical difficulty)?
- Is the dynamic range of the target system sufficient to see the predicted effect?

Output JSON:
- "verdict": "survives" | "vulnerable" | "fatal"
- "attack": string (specific practical concern, 2-3 sentences)
- "bottleneck": string (single biggest practical obstacle)
- "estimated_difficulty": "straightforward" | "challenging" | "heroic"
- "what_would_change_my_mind": string"""
    },
    {
        "id": "impact",
        "name": "Impact",
        "color": "#F59E0B",
        "role": "Assess payoff and novelty",
        "prompt": """You are a grant reviewer evaluating the potential impact of this translation.

Consider:
- If this translation works, what would it actually reveal?
- Is this a genuinely new insight, or something the field already knows/assumes?
- Would this open a new research direction or just confirm existing knowledge?
- Is the juice worth the squeeze (effort vs. insight gained)?

Output JSON:
- "verdict": "survives" | "vulnerable" | "fatal"
- "attack": string (honest assessment, 2-3 sentences)
- "novelty": "high" | "moderate" | "low"
- "potential_impact": string (what this could lead to if it works)
- "what_would_change_my_mind": string"""
    },
]
```

**`run_adversarial(translation, source_context, target_context)`** — Runs all 4 agents in parallel against a single translation. Returns verdicts + survival score (count of survives).

**Commit:** `feat: add adversarial stress-test agents`

---

### Task 5: Chat — Interactive Refinement

**Files:**
- Create: `backend/co_researcher/chat.py`

**What to do:**

A chat agent that takes the full analysis context (both papers, all translations, all adversarial results) and handles researcher queries. The researcher provides constraints, asks questions, or pushes back — the agent refines translations accordingly.

```python
def build_chat_context(source_context, target_context, translations, adversarial_results):
    """Build the system prompt for the chat agent with full analysis context."""
    # ... serialize all context into a structured prompt

def handle_chat_message(session_id, user_message, chat_history):
    """Process a researcher's message and return a response.
    May also return updated translations if the message contains constraints.
    """
    # ... GPT call with full context + chat history
    # Returns: {"response": str, "updated_translations": list | None}
```

**Key behavior:**
- Does NOT ask probing questions
- When researcher says "we can't do X because Y" → updates the translation's break-point, suggests alternative L2/L1 mappings
- When researcher asks "what about Z?" → evaluates Z against the abstraction layers
- Maintains chat history in the session

**Commit:** `feat: add interactive refinement chat agent`

---

### Task 6: App — Flask Routes + Pipeline Orchestration

**Files:**
- Rewrite: `backend/co_researcher/app.py`

**What to do:**

Complete rewrite of the Flask app. New pipeline:

**Endpoints:**
- `POST /api/co-researcher/analyze` — accepts `my_research` (1 file) + `papers` (1-5 files). Starts pipeline.
- `GET /api/co-researcher/stream/<session_id>` — SSE stream (keep existing pattern)
- `POST /api/co-researcher/chat/<session_id>` — send chat message, get response

**Pipeline function `run_pipeline(session_id)`:**

```
Phase 1: Parse all documents
  → emit parsing_status events
  → parse_document() for each file (PDF or DOCX)

Phase 2: Context extraction + decomposition
  → emit context_extracted for source and target
  → extract_context(source_text, "source")
  → extract_context(target_text, "target")
  → for each key_method + key_finding in source:
      → decompose_layers(source_context, method)
      → emit layer_extracted for each

Phase 3: Translation attempts
  → for each decomposed insight:
      → translate_insight(source_context, target_context, layers)
      → emit translation_complete with layer-by-layer breakdown

Phase 4: Adversarial stress-test
  → for each translation (parallel per translation):
      → run_adversarial(translation, source_context, target_context)
      → emit agent_verdict for each agent
      → emit adversarial_complete with survival score

Phase 5: Emit results + chat_ready
  → sort translations by survival score
  → emit results_ready
  → emit chat_ready
```

**For multi-paper:** Run phases 1-4 per paper, then do a cross-paper synthesis step (similar to old cross_paper_consolidation but operating on translations instead of themes).

**Session structure:**
```python
sessions[session_id] = {
    "events": Queue(),
    "target_text": "",
    "target_context": {},
    "source_texts": [],       # one per paper
    "source_contexts": [],    # one per paper
    "decompositions": [],     # all layer decompositions
    "translations": [],       # all translation attempts
    "adversarial_results": [], # all stress-test results
    "chat_history": [],       # chat messages
}
```

**Commit:** `feat: rewrite co-researcher app with new translation pipeline`

---

### Task 7: Frontend — Upload Panel + New Phases

**Files:**
- Rewrite: `frontend/components/co-researcher/UploadPanel.tsx`
- Create: `frontend/components/co-researcher/TranslationCard.tsx`
- Create: `frontend/components/co-researcher/AdversarialBadge.tsx`
- Create: `frontend/components/co-researcher/ChatPanel.tsx`
- Rewrite: `frontend/app/co-researcher/page.tsx`

**What to do:**

**UploadPanel.tsx:**
- Left zone: "My Research" (1 PDF or DOCX)
- Right zone: "Papers I Want to Learn From" (1-5 PDF or DOCX)
- Accept `.pdf,.docx,.doc`
- Interface: `onUpload: (myResearch: File, papers: File[]) => void`
- Title: "Translate Research Ideas Into Your Work"
- Subtitle: "Upload your research and papers you want to learn from. AI agents will decompose their methods into transferable principles and map them to your domain."

**TranslationCard.tsx:**
- Displays a single translation proposal
- Expandable layer-by-layer breakdown (L4→L1)
- Each layer shows: source mapping → target mapping, confidence bar, assumption, break-if
- Highlighted break-point (the weakest layer, with amber/red styling)
- "What to test first" callout at bottom
- Survival score badge (shields)

**AdversarialBadge.tsx:**
- Shows 4 agent verdicts as colored icons
- Green shield = survives, amber shield = vulnerable, red X = fatal
- Expandable detail showing each agent's attack + what would change their mind

**ChatPanel.tsx:**
- Simple chat interface below results
- User types message → POST to `/chat/<session_id>` → response streamed
- System messages styled differently from user messages
- When a translation is updated by chat, the corresponding TranslationCard highlights the change

**page.tsx — New phases:**

```typescript
type Phase = 'upload' | 'analyzing' | 'translating' | 'stress_testing' | 'results'
```

State:
```typescript
const [sourceContexts, setSourceContexts] = useState<any[]>([])
const [targetContext, setTargetContext] = useState<any>(null)
const [decompositions, setDecompositions] = useState<any[]>([])
const [translations, setTranslations] = useState<any[]>([])
const [adversarialResults, setAdversarialResults] = useState<any[]>([])
const [chatMessages, setChatMessages] = useState<{role: string, content: string}[]>([])
const [chatReady, setChatReady] = useState(false)
```

SSE handlers map to new event types from the design doc.

Results page layout:
1. Source/target context cards (collapsible)
2. Translation cards sorted by survival score
3. Chat panel at bottom (appears when `chatReady` is true)

**Commit:** `feat: rewrite frontend for research translator`

---

### Task 8: Delete Old Files

**Files:**
- Delete: `backend/co_researcher/agents.py`
- Delete: `backend/co_researcher/tournament.py`
- Delete: `backend/co_researcher/report_generator.py`

Only delete after the new system is working. These are the old 6-agent ELO tournament system that's being replaced by the decomposer + translator + adversarial architecture.

**Commit:** `chore: remove old co-researcher agent/tournament system`

---

## Implementation Order

Tasks 1-5 are independent backend modules — can be built in parallel.
Task 6 (app.py) depends on Tasks 1-5.
Task 7 (frontend) depends on Task 6 for SSE event types.
Task 8 (cleanup) is last.

Recommended sequence for serial execution:
1 → 2 → 3 → 4 → 5 → 6 → 7 → 8
