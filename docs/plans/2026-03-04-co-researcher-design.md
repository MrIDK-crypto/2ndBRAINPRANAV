# Co-Researcher: AI-Powered Protocol Integration Engine

**Date**: 2026-03-04
**Status**: Approved (Design) / In Progress (Implementation)
**URL**: /co-researcher (no auth required)
**Stack**: Next.js 14 (port 3000) + Flask (port 5010) + Azure OpenAI GPT-5 + LlamaParse

---

## Overview

A public portal where researchers upload their protocol and a research paper. The system uses a multi-agent ELO tournament to generate, debate, and rank integration hypotheses - specific ways to incorporate the paper's innovations into the researcher's protocol.

### Why This Beats ChatGPT

ChatGPT gives one answer. Co-Researcher spawns 6 specialist agents with diverse perspectives, generates 20+ hypotheses, runs a tournament where hypotheses debate head-to-head, and surfaces the best ideas with full transparency into why each won or lost. The researcher watches the debate live and can intervene.

---

## System Architecture

```
Frontend (Next.js 14, port 3000)          Backend (Flask, port 5010)
/co-researcher                             /api/co-researcher/*
├── Upload Panel (2 PDFs)           →     ├── PDF Parse (LlamaParse)
├── Agent Generation View           ←SSE──├── Agent Engine (6 parallel GPT-5)
├── Tournament Arena                ←SSE──├── Tournament Engine (ELO matchups)
├── User Controls (pin/reject)      →     ├── Intervention Handler
└── Results + Revised Protocol      ←SSE──└── Report Generator
```

- Separate backend from main 2nd Brain app (5010 vs 5003)
- SSE (Server-Sent Events) for real-time streaming
- No database - stateless, session-based
- No authentication required

---

## Agent System

### 6 Specialist Agents (3D Diversity)

Each agent has: **domain lens** x **methodology specialty** x **personality archetype**

| Agent   | Domain            | Methodology          | Personality  |
|---------|-------------------|----------------------|--------------|
| Alpha   | Biomedical        | Experimental Design  | Innovator    |
| Beta    | Translational     | Statistical Methods  | Conservative |
| Gamma   | Behavioral/Social | Measurement & Data   | Synthesizer  |
| Delta   | Computational     | Reproducibility      | Critic       |
| Epsilon | Clinical          | Ethics & Compliance  | Pragmatist   |
| Zeta    | Cross-disciplinary| Literature Synthesis | Visionary    |

### Hypothesis Output Format

Each agent generates 3-5 structured hypotheses:

```json
{
  "hypothesis_id": "alpha-1",
  "title": "Replace Western blot with mass spec approach from paper",
  "integration_type": "method_replacement | method_addition | parameter_change | design_modification",
  "evidence": "Paper shows 3x sensitivity improvement...",
  "risk_level": "low | medium | high",
  "protocol_sections_affected": ["Section 3.2", "Section 4.1"],
  "implementation_steps": ["Step 1...", "Step 2..."],
  "confidence": 0.85
}
```

All 6 agents run in parallel (6 concurrent Azure OpenAI calls).

---

## ELO Tournament System

1. **Initial rating**: All hypotheses start at ELO 1200
2. **Pairing**: Round-robin subset (~4-5 opponents each, ~40-60 total matchups)
3. **Evaluation**: For each matchup, an evaluator agent (GPT-5) sees both hypotheses + full context
4. **Scoring**: Winner determined with reasoning. Decisive win, narrow win, or draw.
5. **ELO update**: Standard ELO formula with K-factor=32
6. **User intervention**: Pinned hypotheses are protected. Rejected hypotheses are eliminated.
7. **Streaming**: Each matchup result streams live to the frontend

---

## Frontend: 4-Phase Progressive UI

### Phase 1: Upload
- Two drag-and-drop zones side by side ("Your Protocol" + "Research Paper")
- PDF only, parsed by LlamaParse
- Single CTA: "Analyze & Generate Hypotheses"

### Phase 2: Agent Generation
- Cards for each agent appear, fill in as they complete
- Shows agent persona (domain/methodology/personality)
- Hypothesis titles stream in as generated

### Phase 3: Tournament Arena (Star Feature)
- Current matchup displayed prominently with both hypotheses
- Evaluator reasoning streams in real-time
- ELO leaderboard on the side, updates after each matchup
- "Your Picks" panel for pinned/rejected hypotheses
- Controls: Pin, Reject, Skip to Results

### Phase 4: Results
- Top 5 ranked hypotheses with full details
- Each shows: evidence, implementation steps, tournament record, debate history
- Pinned hypotheses included regardless of rank
- Actions: "Generate Revised Protocol", "Download Report (PDF)", "Start New Analysis"

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/co-researcher/analyze` | POST (multipart) | Upload 2 PDFs, returns session_id |
| `/api/co-researcher/stream/{session_id}` | GET (SSE) | Stream all events |
| `/api/co-researcher/pin/{session_id}` | POST | Pin a hypothesis |
| `/api/co-researcher/reject/{session_id}` | POST | Reject a hypothesis |
| `/api/co-researcher/report/{session_id}` | POST | Generate final report |
| `/api/co-researcher/health` | GET | Health check |

### SSE Event Types

| Event | Data |
|-------|------|
| `parsing_status` | `{stage, progress, message}` |
| `agent_started` | `{agent_id, name, domain, personality}` |
| `hypothesis_generated` | `{agent_id, hypothesis: {...}}` |
| `agent_complete` | `{agent_id, hypothesis_count}` |
| `tournament_started` | `{total_hypotheses, total_matchups}` |
| `matchup_result` | `{round, hypothesis_a, hypothesis_b, winner, reasoning, score, elo_updates}` |
| `leaderboard_update` | `{rankings: [{id, elo, change}]}` |
| `tournament_complete` | `{final_rankings}` |
| `report_ready` | `{recommendations, revised_protocol}` |

---

## External Services

| Service | Purpose | Key |
|---------|---------|-----|
| LlamaParse | High-quality PDF extraction | `llx-kxyquEwhrd9z5QeQWtrGeHh2dwbAzqDz34nP1dSh4qo6iAhL` |
| Azure OpenAI GPT-5 | Agent generation, evaluation, report | Existing Azure deployment |
| Azure OpenAI text-embedding-3-large | (optional future: semantic similarity) | Existing Azure deployment |

---

## Cost Per Analysis

| Step | API Calls | Estimated Cost |
|------|-----------|----------------|
| Parse 2 PDFs | 2 LlamaParse | ~$0.006 |
| 6 agent hypothesis generation | 6 GPT-5 | ~$0.50 |
| ~48 tournament matchups | 48 GPT-5 | ~$1.20 |
| Report + revised protocol | 2 GPT-5 | ~$0.30 |
| **Total** | **~58 calls** | **~$2.00** |

---

## File Structure (New)

```
frontend/
  app/co-researcher/
    page.tsx                    # Main page component
  components/co-researcher/
    UploadPanel.tsx             # Phase 1: PDF upload
    AgentGenerationView.tsx     # Phase 2: Agent cards streaming
    TournamentArena.tsx         # Phase 3: Live debate + ELO
    ResultsPanel.tsx            # Phase 4: Final recommendations
    EloLeaderboard.tsx          # Sortable ELO rankings
    MatchupCard.tsx             # Single matchup display
    HypothesisCard.tsx          # Hypothesis detail card

backend/
  co_researcher/
    app.py                      # Flask app (port 5010)
    agents.py                   # Agent definitions + prompts
    tournament.py               # ELO tournament engine
    parser.py                   # LlamaParse integration
    report_generator.py         # Final report + revised protocol
```
