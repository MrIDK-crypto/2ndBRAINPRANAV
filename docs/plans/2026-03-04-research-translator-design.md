# Research Translator — Design Document

## Problem

A researcher reads a paper from another field. They sense something useful is buried in it but can't extract the transferable skeleton from the field-specific details. Current tools generate surface-level analogies and can't tell you whether a translation would actually work in your system.

## Core Question

**"I read this paper. Here's my research. How do I use their ideas in my work?"**

Not protocol integration. Not literature review. Cross-domain methodological translation.

## Input / Output

**Input:**
- "My research" — PDF or DOCX (their paper, manuscript draft, or research description)
- "Paper I want to learn from" — PDF or DOCX (1-5 papers from any field)

**Output:**
- 3-5 concrete translation proposals
- Each decomposed into abstraction layers (principle → logic → design → implementation)
- Each with explicit break-point analysis (where does the mapping fail?)
- Each adversarially stress-tested by 4 role-based agents
- Ranked by survival score (feasibility x novelty x impact)
- Interactive refinement chat after initial analysis

---

## Pipeline Architecture

### Phase 1: Deep Parse + Context Extraction

Parse both sides. For each document, extract structured context:

**Source paper (the one they read):**
```json
{
  "domain": "developmental biology / pattern formation",
  "key_methods": [
    {
      "name": "Hox allelic series",
      "what_it_does": "Graded genetic perturbation across multiple backgrounds",
      "why_it_matters": "Turns binary genetic tool into continuous parameter scan",
      "specific_implementation": "Hox13 compound mutants in mouse limbs"
    }
  ],
  "key_findings": [
    {
      "finding": "Digit wavelength is modulated by Hox13 dosage",
      "evidence_type": "genetic + computational",
      "supporting_data": "Figure 3: allelic series shows graded wavelength change"
    }
  ],
  "analytical_approaches": ["reaction-diffusion modeling", "parameter sensitivity analysis"],
  "conceptual_principles": ["self-organizing systems can be characterized by smoothly tuning their parameters"]
}
```

**Target paper (their own research):**
```json
{
  "domain": "iron homeostasis / ubiquitin biology",
  "experimental_systems": ["HEK293 cells", "mouse models", "Western blot", "IP"],
  "available_techniques": ["CRISPR", "ubiquitin assays", "iron measurement"],
  "key_regulatory_circuit": "FBXL5 senses iron+oxygen → targets IRP1/2 for degradation",
  "open_questions": ["Is FBXL5-CIA interaction graded or switch-like?"],
  "limitations_acknowledged": ["unclear mechanism of oxygen sensing integration"]
}
```

This replaces the old `assess_relevance()`. Instead of a 0-1 score, we get structured context for both sides.

### Phase 2: Abstraction Layer Decomposition

For each key method/finding in the source paper, decompose into 4 layers:

| Layer | Name | Description | Example (Turing paper) |
|-------|------|-------------|----------------------|
| L4 | Principle | Field-agnostic conceptual insight | "Self-organizing systems can be characterized by smoothly tuning their parameters" |
| L3 | Analytical Logic | Reasoning pattern connecting data to conclusion | "Continuous dose-response reveals parameter modulation of a system" |
| L2 | Design Pattern | Experimental design structure | "Graded genetic perturbation across multiple backgrounds" |
| L1 | Implementation | Specific reagents, organisms, measurements | "Hox13 allelic series in mouse limbs, measured by digit number/wavelength" |

This decomposition is done by a single GPT call per method/finding. The prompt must explicitly distinguish layers and refuse to conflate them.

### Phase 3: Translation Attempts

For each L4/L3 insight, attempt top-down re-instantiation into the target domain. For each layer downward, the system:

1. Proposes the mapping
2. States what assumptions the mapping requires
3. Flags where the mapping might break

Output per translation:

```json
{
  "source_insight": "Smooth parameter tuning reveals system operating logic",
  "layers": [
    {
      "level": "L4",
      "source": "Self-organizing systems characterized by parameter tuning",
      "target": "Iron homeostasis circuit may have tunable parameters (FBXL5 dosage)",
      "confidence": 0.8,
      "assumption": "The FBXL5-IRP circuit has graded behavior, not just on/off",
      "breaks_if": "FBXL5-CIA interaction is cooperative and binary"
    },
    {
      "level": "L3",
      "source": "Dose-response reveals parameter modulation",
      "target": "Vary FBXL5/CIA dosage continuously, measure IRP1/2 levels",
      "confidence": 0.6,
      "assumption": "IRP1/2 protein levels change gradually with FBXL5 dose",
      "breaks_if": "System is bistable — cells flip between states with no graded middle"
    },
    {
      "level": "L2",
      "source": "Allelic series across multiple backgrounds",
      "target": "CRISPR graded FBXL5 mutants: het, hypomorph, CTBD-del, CIA haploinsufficiency",
      "confidence": 0.4,
      "assumption": "You can generate 4+ distinct dosage levels of FBXL5",
      "breaks_if": "CTBD mutations are all-or-nothing, can't get intermediate binding"
    },
    {
      "level": "L1",
      "source": "Mouse limbs, digit counting",
      "target": "HEK293 cells, Western blot for IRP1/2 at each dosage point",
      "confidence": 0.7,
      "assumption": "HEK293 has active iron regulatory circuit",
      "breaks_if": "Cell line doesn't express relevant CIA components"
    }
  ],
  "overall_break_point": "L2 — the graded mutant series is the bottleneck",
  "what_to_test_first": "Check if heterozygous FBXL5 KO shows intermediate IRP levels. If yes, the translation likely works. If IRP levels are unchanged until full KO, the system is switch-like and this translation fails."
}
```

**Key design choice:** Each translation explicitly identifies its **weakest layer** and **what experiment would resolve the uncertainty**. This is the most valuable output — not "here are ideas" but "here's exactly what you'd need to test to know if this works."

### Phase 4: Adversarial Stress-Test

4 role-based agents attack each translation proposal. This replaces the 6-agent ELO tournament.

| Agent | Role | What it evaluates |
|-------|------|-------------------|
| **Skeptic** | Break the translation | "What assumption does this require that might not hold?" Looks for the weakest layer, checks if the mapping is forced |
| **Prior Art** | Check novelty + precedent | Searches for bridge papers connecting the two domains. "Has anyone tried this?" "Did it work or fail?" Uses web search |
| **Feasibility** | Practical constraints | "Do the reagents exist? Is the dynamic range sufficient? What's the experimental bottleneck?" Uses target paper's methods as proxy for lab capabilities |
| **Impact** | Assess payoff | "If this works, what does it actually tell you that you don't already know? Is this a marginal improvement or a new avenue?" |

Each agent outputs:
```json
{
  "agent": "skeptic",
  "verdict": "vulnerable",  // "survives" | "vulnerable" | "fatal"
  "attack": "The FBXL5-CIA interaction is mediated by cysteine coordination which is typically cooperative/binary, not graded. The L2 mapping assumes graded binding but the biochemistry likely doesn't support it.",
  "what_would_change_my_mind": "Show FBXL5 CTBD point mutants with measurably different CIA binding affinities"
}
```

**Survival scoring:**
- 4 survives = strong proposal (score 4)
- 3 survives + 1 vulnerable = viable with caveats (score 3)
- Any fatal = proposal flagged but not killed (user decides)
- Score displayed as shields: 🛡🛡🛡🛡 or 🛡🛡🛡⚠

### Phase 5: Interactive Refinement (Chat)

After initial analysis, transition to a chat interface. The system:
- Presents top 3-5 translations ranked by survival score
- Waits for researcher input (not prompting with questions)
- When the researcher provides constraints ("we can't do X because Y"), the system:
  - Updates the translation's break-point analysis
  - Re-runs relevant adversarial checks
  - May propose alternative L2/L1 instantiations that avoid the constraint

**Design principle:** The system does NOT ask a lot of questions. It presents its best analysis and waits. When the researcher speaks, it refines. The interaction is researcher-driven, not system-driven.

The chat uses the same SSE stream. New event types:
- `chat_message` — system sends a message
- `translation_updated` — a translation was refined based on user input
- `agent_recheck` — an adversarial agent re-evaluated after constraint

---

## Agent Architecture (replacing the old 6 agents)

### Old (Co-Researcher v1)
6 category-specialist agents (Experimental, Statistical, Measurement, Computational, Practical, Cross-Disciplinary) each generating 3 hypotheses → 18 hypotheses → ELO tournament

### New (Research Translator)
**Phase 2-3:** Single decomposition+translation agent (one GPT call per source method/finding). No need for 6 parallel agents — the decomposition is systematic, not opinion-based.

**Phase 4:** 4 role-based adversarial agents running in parallel against each translation. These ARE parallel because they evaluate different dimensions independently.

**Phase 5:** Single chat agent with full context (both papers + all translations + adversarial results).

### Why this is better
- Old system generated 18 variations of "here's how to integrate" and debated which is best
- New system generates 3-5 structurally distinct translations (because they come from different L4 insights) and stress-tests each one
- The tournament was comparing apples — the adversarial test is breaking apples

---

## Backend File Structure

```
backend/co_researcher/
├── app.py              # Flask routes + SSE (REWRITE)
├── parser.py           # PDF + DOCX parsing (MODIFY: add DOCX support)
├── decomposer.py       # NEW: Phase 1-2 (context extraction + layer decomposition)
├── translator.py       # NEW: Phase 3 (cross-domain translation attempts)
├── adversarial.py      # NEW: Phase 4 (4 stress-test agents)
├── chat.py             # NEW: Phase 5 (interactive refinement)
└── __init__.py
```

**Deleted files:** `agents.py` (old 6-agent system), `tournament.py` (ELO system), `report_generator.py` (old report generation)

**Reused:** `parser.py` (LlamaParse), `azure_openai_config.py` (Azure client)

---

## Frontend Architecture

```
frontend/
├── app/co-researcher/page.tsx        # REWRITE: new phases + chat UI
└── components/co-researcher/
    ├── UploadPanel.tsx               # MODIFY: accept PDF + DOCX, "my research" + "papers I read"
    ├── TranslationCard.tsx           # NEW: single translation with layer breakdown
    ├── AdversarialBadge.tsx          # NEW: survival score display
    └── ChatPanel.tsx                 # NEW: interactive refinement chat
```

### New UI Phases

1. **Upload** — "My Research" (1 file) + "Papers I Read" (1-5 files)
2. **Analyzing** — Shows parsing → context extraction → decomposition progress
3. **Translating** — Shows each L4 insight being translated down through layers, with break-points appearing in real-time
4. **Stress-Testing** — 4 agents attack each translation, verdicts appear live
5. **Results** — Translation cards ranked by survival score, with expandable layer details
6. **Chat** — Inline refinement below results (not a separate page)

---

## SSE Event Types

### Phase 1-2
- `parsing_status` — file being parsed
- `context_extracted` — structured context for source/target paper
- `decomposition_started` — beginning layer decomposition
- `layer_extracted` — a single L4/L3/L2/L1 layer extracted from source paper
- `decomposition_complete` — all layers extracted

### Phase 3
- `translation_started` — beginning translation attempt for an L4 insight
- `translation_layer` — a single layer mapping proposed (streamed as they're generated)
- `translation_complete` — full translation with break-point identified

### Phase 4
- `adversarial_started` — stress-testing a translation
- `agent_verdict` — single agent's verdict on a translation
- `adversarial_complete` — all 4 agents done, survival score calculated

### Phase 5
- `chat_ready` — interactive refinement available
- `chat_response` — system response to user input
- `translation_updated` — translation refined based on user constraint

---

## Key Design Decisions

### 1. No ELO tournament
The old tournament compared which hypothesis is "better" within a category. That's the wrong question. The right question is "does this translation survive scrutiny?" The adversarial test answers that directly.

### 2. Break-points > relevance scores
A 0-1 relevance score is useless. "This paper is 35% relevant" tells you nothing. "This translation works at L4 and L3 but breaks at L2 because the biochemistry is binary not graded" — that's actionable.

### 3. Chat is researcher-driven
The system presents, the researcher responds. No "please tell me about your lab" questionnaires. The system's first analysis should be good enough to be useful without any interaction. The chat makes it better, not acceptable.

### 4. Prior Art agent uses web search
This is the only agent that reaches outside the uploaded documents. It searches for bridge papers: "has anyone applied reaction-diffusion modeling to ubiquitin regulatory circuits?" Finding precedent (or lack thereof) is the strongest signal for feasibility.

### 5. DOCX support via python-docx
Already available in the backend parser. LlamaParse handles PDFs. For DOCX, fall through to python-docx. The co_researcher parser.py just needs a `parse_document()` that dispatches by extension.

---

## What We Keep

- **Flask + SSE streaming** — same architecture, just different events
- **LlamaParse** — PDF parsing unchanged
- **Azure OpenAI (GPT-5)** — all LLM calls, same config
- **Next.js + React frontend** — same framework
- **Warm cream design system** — same tokens (Manrope, #ea580c accent, #f5f3f0 bg)
- **Multi-paper support** — "Papers I Read" accepts 1-5

## What We Delete

- 6 category-specialist agents (Alpha through Zeta)
- ELO tournament system
- Category-based matchups
- Debiased evaluation
- Theme consolidation across categories
- "Protocol integration report"
- "Protocol modifications" section

---

## Cost Estimate (per analysis, 1 protocol + 1 paper)

| Step | GPT calls | Est. tokens |
|------|-----------|-------------|
| Context extraction (2 papers) | 2 | ~20K in, ~2K out |
| Layer decomposition (3-5 methods) | 4 | ~15K in, ~3K out |
| Translation attempts (3-5) | 4 | ~12K in, ~4K out |
| Adversarial (4 agents x 4 translations) | 16 | ~60K in, ~8K out |
| **Total** | ~26 | ~107K in, ~17K out |

Old system: ~30+ calls (6 agents x 3 hyps + 18 verifications + ~15 matchups + consolidation + report). Comparable cost, much better output structure.
