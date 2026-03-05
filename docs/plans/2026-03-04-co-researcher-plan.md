# Co-Researcher Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a no-login portal at `/co-researcher` where researchers upload their protocol + a research paper, and a 6-agent ELO tournament system generates, debates, and ranks integration hypotheses in real-time.

**Architecture:** Separate Flask backend (port 5010) with SSE streaming to Next.js 14 frontend. LlamaParse for PDF parsing, Azure OpenAI GPT-5 for all agent LLM calls. In-memory session state (no database). Frontend has 4 progressive phases: Upload -> Agent Generation -> Tournament Arena -> Results.

**Tech Stack:** Next.js 14 + React 18 + Tailwind CSS (frontend), Flask + flask-cors + openai SDK (backend), LlamaParse API, Azure OpenAI (gpt-5-chat deployment)

**Design Doc:** `docs/plans/2026-03-04-co-researcher-design.md`

---

## Task 1: Backend - Flask App Skeleton + Health Check

**Files:**
- Create: `backend/co_researcher/app.py`
- Create: `backend/co_researcher/__init__.py`

**Step 1: Create the Flask app with CORS and health endpoint**

```python
# backend/co_researcher/__init__.py
# (empty file)
```

```python
# backend/co_researcher/app.py
import os
import uuid
import json
import threading
from queue import Queue
from flask import Flask, request, jsonify, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/api/*": {
    "origins": ["http://localhost:3000", "http://localhost:3006"],
    "methods": ["GET", "POST", "OPTIONS"],
    "allow_headers": ["Content-Type"]
}})

# In-memory session store
# session_id -> { "events": Queue, "hypotheses": {}, "pinned": set, "rejected": set, "protocol": str, "paper": str }
sessions = {}

@app.route('/api/co-researcher/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "co-researcher"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5010, debug=True)
```

**Step 2: Test it runs**

Run: `cd backend && python -m co_researcher.app`
Expected: Flask starts on port 5010

Run: `curl http://localhost:5010/api/co-researcher/health`
Expected: `{"status": "ok", "service": "co-researcher"}`

**Step 3: Commit**

```bash
git add backend/co_researcher/
git commit -m "feat(co-researcher): Flask app skeleton with health check"
```

---

## Task 2: Backend - LlamaParse PDF Parser

**Files:**
- Create: `backend/co_researcher/parser.py`

**Step 1: Implement LlamaParse integration**

The LlamaParse API is a REST API. Upload a file, get back a job ID, poll until complete, download markdown result.

```python
# backend/co_researcher/parser.py
import os
import time
import requests

LLAMAPARSE_API_KEY = os.getenv("LLAMAPARSE_API_KEY", "llx-kxyquEwhrd9z5QeQWtrGeHh2dwbAzqDz34nP1dSh4qo6iAhL")
LLAMAPARSE_BASE_URL = "https://api.cloud.llamaindex.ai/api/v1/parsing"

def parse_pdf(file_bytes: bytes, filename: str) -> str:
    """
    Parse a PDF using LlamaParse API.
    Returns extracted text as markdown.
    """
    headers = {
        "Authorization": f"Bearer {LLAMAPARSE_API_KEY}",
    }

    # Step 1: Upload the file
    files = {
        "file": (filename, file_bytes, "application/pdf"),
    }
    data = {
        "result_type": "markdown",
        "language": "en",
    }

    upload_resp = requests.post(
        f"{LLAMAPARSE_BASE_URL}/upload",
        headers=headers,
        files=files,
        data=data,
        timeout=60
    )
    upload_resp.raise_for_status()
    job_id = upload_resp.json()["id"]

    # Step 2: Poll for completion (max 5 minutes)
    for _ in range(60):
        status_resp = requests.get(
            f"{LLAMAPARSE_BASE_URL}/job/{job_id}",
            headers=headers,
            timeout=30
        )
        status_resp.raise_for_status()
        status = status_resp.json()["status"]

        if status == "SUCCESS":
            break
        elif status == "ERROR":
            raise RuntimeError(f"LlamaParse failed for {filename}: {status_resp.json()}")

        time.sleep(5)
    else:
        raise TimeoutError(f"LlamaParse timed out for {filename}")

    # Step 3: Download result
    result_resp = requests.get(
        f"{LLAMAPARSE_BASE_URL}/job/{job_id}/result/markdown",
        headers=headers,
        timeout=30
    )
    result_resp.raise_for_status()
    return result_resp.json()["markdown"]
```

**Step 2: Test with a real PDF (manual)**

```python
# Quick test script
from co_researcher.parser import parse_pdf
with open("test.pdf", "rb") as f:
    text = parse_pdf(f.read(), "test.pdf")
print(text[:500])
```

**Step 3: Commit**

```bash
git add backend/co_researcher/parser.py
git commit -m "feat(co-researcher): LlamaParse PDF parser integration"
```

---

## Task 3: Backend - Agent Definitions + Hypothesis Generation

**Files:**
- Create: `backend/co_researcher/agents.py`

**Step 1: Define the 6 agent personas and hypothesis generation**

Reference: Use `backend/azure_openai_config.py` for Azure OpenAI client creation. Import `get_azure_client` and `AZURE_CHAT_DEPLOYMENT` from there.

```python
# backend/co_researcher/agents.py
import json
import sys
import os

# Add parent directory to path so we can import azure_openai_config
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from azure_openai_config import get_azure_client, AZURE_CHAT_DEPLOYMENT

AGENTS = [
    {
        "id": "alpha",
        "name": "Alpha",
        "domain": "Biomedical",
        "methodology": "Experimental Design",
        "personality": "Innovator",
        "color": "#EF4444",  # red
        "description": "Pushes bold integrations, novel combinations of techniques"
    },
    {
        "id": "beta",
        "name": "Beta",
        "domain": "Translational",
        "methodology": "Statistical Methods",
        "personality": "Conservative",
        "color": "#3B82F6",  # blue
        "description": "Minimal safe changes, evidence-heavy approach"
    },
    {
        "id": "gamma",
        "name": "Gamma",
        "domain": "Behavioral/Social",
        "methodology": "Measurement & Data Collection",
        "personality": "Synthesizer",
        "color": "#10B981",  # green
        "description": "Finds middle ground, combines ideas from both documents"
    },
    {
        "id": "delta",
        "name": "Delta",
        "domain": "Computational",
        "methodology": "Reproducibility & Validation",
        "personality": "Critic",
        "color": "#F59E0B",  # amber
        "description": "Stress-tests feasibility, finds flaws in proposed integrations"
    },
    {
        "id": "epsilon",
        "name": "Epsilon",
        "domain": "Clinical",
        "methodology": "Ethics & Compliance",
        "personality": "Pragmatist",
        "color": "#8B5CF6",  # purple
        "description": "Practical implementation focus, regulatory awareness"
    },
    {
        "id": "zeta",
        "name": "Zeta",
        "domain": "Cross-disciplinary",
        "methodology": "Literature Synthesis",
        "personality": "Visionary",
        "color": "#EC4899",  # pink
        "description": "Big-picture connections, cross-field insights"
    },
]


def _build_agent_system_prompt(agent: dict) -> str:
    return f"""You are a research integration specialist with the following profile:

DOMAIN EXPERTISE: {agent['domain']}
METHODOLOGY SPECIALTY: {agent['methodology']}
PERSONALITY ARCHETYPE: {agent['personality']} - {agent['description']}

Your task: Given a researcher's existing protocol and a new research paper, propose specific integration hypotheses - concrete ways to incorporate innovations, methods, or findings from the paper into the existing protocol.

For each hypothesis, provide:
1. A clear, specific title
2. The type of integration (method_replacement, method_addition, parameter_change, or design_modification)
3. Evidence from the paper supporting this integration
4. Risk level (low, medium, high)
5. Which sections of the protocol would be affected
6. Step-by-step implementation instructions
7. Your confidence score (0.0 to 1.0)

Your {agent['personality'].lower()} personality should strongly influence your proposals:
- If Innovator: Push bold, unconventional integrations. Propose novel combinations.
- If Conservative: Only propose well-evidenced, minimal-risk changes. Err on caution.
- If Synthesizer: Find elegant ways to merge approaches from both documents.
- If Critic: Focus on what could go wrong. Propose integrations that address weaknesses.
- If Pragmatist: Focus on what's actually implementable given real-world constraints.
- If Visionary: Think big-picture. Connect ideas across disciplines.

Generate exactly 4 hypotheses. Output ONLY valid JSON array."""


def _build_agent_user_prompt(protocol_text: str, paper_text: str) -> str:
    # Truncate to stay within token limits (~50K chars each = ~12K tokens each)
    max_chars = 50000
    protocol_truncated = protocol_text[:max_chars]
    paper_truncated = paper_text[:max_chars]

    return f"""## RESEARCHER'S EXISTING PROTOCOL

{protocol_truncated}

---

## NEW RESEARCH PAPER

{paper_truncated}

---

Generate 4 integration hypotheses as a JSON array. Each hypothesis must have these exact fields:
- "title": string (specific, actionable title)
- "integration_type": one of "method_replacement", "method_addition", "parameter_change", "design_modification"
- "evidence": string (evidence from the paper supporting this)
- "risk_level": one of "low", "medium", "high"
- "protocol_sections_affected": array of strings (which parts of the protocol change)
- "implementation_steps": array of strings (step-by-step how to integrate)
- "confidence": number between 0.0 and 1.0

Return ONLY the JSON array, no other text."""


def generate_hypotheses(agent: dict, protocol_text: str, paper_text: str) -> list:
    """
    Generate integration hypotheses for a single agent.
    Returns list of hypothesis dicts with agent metadata attached.
    """
    client = get_azure_client()

    response = client.chat.completions.create(
        model=AZURE_CHAT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": _build_agent_system_prompt(agent)},
            {"role": "user", "content": _build_agent_user_prompt(protocol_text, paper_text)},
        ],
        temperature=0.8,  # Higher temp for diverse hypotheses
        max_tokens=4000,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    parsed = json.loads(raw)

    # Handle both {"hypotheses": [...]} and [...] formats
    if isinstance(parsed, dict):
        hypotheses = parsed.get("hypotheses", parsed.get("results", []))
    elif isinstance(parsed, list):
        hypotheses = parsed
    else:
        hypotheses = []

    # Attach agent metadata and IDs
    for i, h in enumerate(hypotheses):
        h["hypothesis_id"] = f"{agent['id']}-{i+1}"
        h["agent_id"] = agent["id"]
        h["agent_name"] = agent["name"]
        h["agent_domain"] = agent["domain"]
        h["agent_personality"] = agent["personality"]
        h["agent_color"] = agent["color"]

    return hypotheses
```

**Step 2: Commit**

```bash
git add backend/co_researcher/agents.py
git commit -m "feat(co-researcher): 6 specialist agent definitions + hypothesis generation"
```

---

## Task 4: Backend - ELO Tournament Engine

**Files:**
- Create: `backend/co_researcher/tournament.py`

**Step 1: Implement ELO tournament with evaluator agent**

```python
# backend/co_researcher/tournament.py
import json
import random
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from azure_openai_config import get_azure_client, AZURE_CHAT_DEPLOYMENT


def calculate_elo(winner_elo: float, loser_elo: float, k: int = 32, draw: bool = False) -> tuple:
    """
    Standard ELO calculation. Returns (new_winner_elo, new_loser_elo).
    """
    expected_winner = 1.0 / (1.0 + 10 ** ((loser_elo - winner_elo) / 400))
    expected_loser = 1.0 - expected_winner

    if draw:
        new_winner = winner_elo + k * (0.5 - expected_winner)
        new_loser = loser_elo + k * (0.5 - expected_loser)
    else:
        new_winner = winner_elo + k * (1.0 - expected_winner)
        new_loser = loser_elo + k * (0.0 - expected_loser)

    return round(new_winner), round(new_loser)


def generate_matchups(hypothesis_ids: list, rounds_per_hypothesis: int = 4) -> list:
    """
    Generate tournament matchups. Each hypothesis faces ~rounds_per_hypothesis opponents.
    Returns list of (id_a, id_b) tuples.
    """
    matchups = []
    n = len(hypothesis_ids)
    if n < 2:
        return []

    # Generate round-robin subset
    all_pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            all_pairs.append((hypothesis_ids[i], hypothesis_ids[j]))

    random.shuffle(all_pairs)

    # Target: each hypothesis appears in ~rounds_per_hypothesis matchups
    target_total = (n * rounds_per_hypothesis) // 2
    matchups = all_pairs[:target_total]

    return matchups


EVALUATOR_SYSTEM_PROMPT = """You are an expert research evaluator. Your job is to compare two integration hypotheses and determine which one is stronger.

Consider these criteria:
1. SCIENTIFIC RIGOR: Is the evidence from the paper strong? Is the reasoning sound?
2. FEASIBILITY: Can this actually be implemented in the protocol?
3. IMPACT: How much would this improve the protocol?
4. RISK/BENEFIT: Does the benefit outweigh the risk?
5. SPECIFICITY: Is the hypothesis concrete and actionable?

You must output a JSON object with:
- "winner": "a" or "b" or "draw"
- "score": "decisive" (clear winner) or "narrow" (close) or "draw"
- "reasoning": A 2-3 sentence explanation of your judgment
- "criteria_scores": {"a": {"rigor": 1-5, "feasibility": 1-5, "impact": 1-5}, "b": {"rigor": 1-5, "feasibility": 1-5, "impact": 1-5}}

Output ONLY valid JSON."""


def evaluate_matchup(
    hypothesis_a: dict,
    hypothesis_b: dict,
    protocol_summary: str,
    paper_summary: str
) -> dict:
    """
    Run a head-to-head evaluation of two hypotheses.
    Returns evaluation result dict.
    """
    client = get_azure_client()

    user_prompt = f"""## Context
Protocol summary: {protocol_summary[:3000]}
Paper summary: {paper_summary[:3000]}

## Hypothesis A: "{hypothesis_a['title']}"
Agent: {hypothesis_a.get('agent_name', '?')} ({hypothesis_a.get('agent_personality', '?')})
Type: {hypothesis_a.get('integration_type', '?')}
Evidence: {hypothesis_a.get('evidence', '?')}
Risk: {hypothesis_a.get('risk_level', '?')}
Steps: {json.dumps(hypothesis_a.get('implementation_steps', []))}
Confidence: {hypothesis_a.get('confidence', '?')}

## Hypothesis B: "{hypothesis_b['title']}"
Agent: {hypothesis_b.get('agent_name', '?')} ({hypothesis_b.get('agent_personality', '?')})
Type: {hypothesis_b.get('integration_type', '?')}
Evidence: {hypothesis_b.get('evidence', '?')}
Risk: {hypothesis_b.get('risk_level', '?')}
Steps: {json.dumps(hypothesis_b.get('implementation_steps', []))}
Confidence: {hypothesis_b.get('confidence', '?')}

Compare these two hypotheses. Which is a stronger integration recommendation?"""

    response = client.chat.completions.create(
        model=AZURE_CHAT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": EVALUATOR_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,  # Lower temp for consistent judging
        max_tokens=500,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content
    result = json.loads(raw)
    return result
```

**Step 2: Commit**

```bash
git add backend/co_researcher/tournament.py
git commit -m "feat(co-researcher): ELO tournament engine with evaluator agent"
```

---

## Task 5: Backend - Report Generator

**Files:**
- Create: `backend/co_researcher/report_generator.py`

**Step 1: Implement report and revised protocol generation**

```python
# backend/co_researcher/report_generator.py
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from azure_openai_config import get_azure_client, AZURE_CHAT_DEPLOYMENT


def generate_report(
    top_hypotheses: list,
    pinned_hypotheses: list,
    protocol_text: str,
    paper_text: str,
    debate_history: list
) -> dict:
    """
    Generate a structured recommendations report from the top-ranked hypotheses.
    """
    client = get_azure_client()

    all_recommendations = top_hypotheses + [h for h in pinned_hypotheses if h not in top_hypotheses]

    hypotheses_text = ""
    for i, h in enumerate(all_recommendations):
        hypotheses_text += f"""
### Recommendation {i+1}: {h['title']}
- ELO Rating: {h.get('elo', 1200)}
- Agent: {h.get('agent_name', '?')} ({h.get('agent_personality', '?')})
- Type: {h.get('integration_type', '?')}
- Risk: {h.get('risk_level', '?')}
- Evidence: {h.get('evidence', '?')}
- Steps: {json.dumps(h.get('implementation_steps', []))}
- Tournament Record: {h.get('wins', 0)}W-{h.get('losses', 0)}L
"""

    response = client.chat.completions.create(
        model=AZURE_CHAT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": """You are an expert research protocol consultant. Generate a comprehensive integration report based on the tournament results. Structure the report with:
1. Executive Summary (2-3 sentences)
2. Top Recommendations (numbered, with priority/risk/impact for each)
3. Implementation Roadmap (suggested order of integration)
4. Risk Assessment (what could go wrong, mitigation strategies)
5. Expected Outcomes (how the protocol improves)

Write in clear, professional academic language. Be specific and actionable."""},
            {"role": "user", "content": f"""Protocol (first 5000 chars):
{protocol_text[:5000]}

Paper (first 5000 chars):
{paper_text[:5000]}

Tournament-Ranked Recommendations:
{hypotheses_text}

Generate the integration report."""},
        ],
        temperature=0.4,
        max_tokens=3000,
    )

    return {
        "report_markdown": response.choices[0].message.content,
        "recommendations": all_recommendations,
    }


def generate_revised_protocol(
    top_hypotheses: list,
    protocol_text: str,
) -> str:
    """
    Generate a revised version of the protocol incorporating the top hypotheses.
    """
    client = get_azure_client()

    changes_text = "\n".join([
        f"- {h['title']}: {json.dumps(h.get('implementation_steps', []))}"
        for h in top_hypotheses
    ])

    response = client.chat.completions.create(
        model=AZURE_CHAT_DEPLOYMENT,
        messages=[
            {"role": "system", "content": """You are an expert protocol editor. Revise the given research protocol by integrating the recommended changes.

Mark ALL modifications with [ADDED] or [MODIFIED] tags so the researcher can see exactly what changed. Preserve the original structure and formatting as much as possible. Only change sections that are directly affected by the recommendations."""},
            {"role": "user", "content": f"""Original Protocol:
{protocol_text[:30000]}

Changes to integrate:
{changes_text}

Generate the revised protocol with tracked changes."""},
        ],
        temperature=0.3,
        max_tokens=6000,
    )

    return response.choices[0].message.content
```

**Step 2: Commit**

```bash
git add backend/co_researcher/report_generator.py
git commit -m "feat(co-researcher): report + revised protocol generator"
```

---

## Task 6: Backend - Main Pipeline with SSE Streaming

**Files:**
- Modify: `backend/co_researcher/app.py`

**Step 1: Add the full analysis pipeline with SSE streaming**

Replace the entire `app.py` with the complete version that wires together parser, agents, tournament, and report generator. Key additions:

- `POST /api/co-researcher/analyze` - accepts 2 PDFs, creates session, starts pipeline in background thread
- `GET /api/co-researcher/stream/<session_id>` - SSE endpoint that drains the session event queue
- `POST /api/co-researcher/pin/<session_id>` - pin a hypothesis
- `POST /api/co-researcher/reject/<session_id>` - reject a hypothesis
- `POST /api/co-researcher/report/<session_id>` - generate final report

The pipeline runs in a background thread. It pushes events into a `Queue` on the session. The SSE endpoint reads from that queue and streams events to the frontend.

```python
# backend/co_researcher/app.py
import os
import uuid
import json
import time
import threading
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor, as_completed

from flask import Flask, request, jsonify, Response
from flask_cors import CORS

from co_researcher.parser import parse_pdf
from co_researcher.agents import AGENTS, generate_hypotheses
from co_researcher.tournament import generate_matchups, evaluate_matchup, calculate_elo
from co_researcher.report_generator import generate_report, generate_revised_protocol

app = Flask(__name__)
CORS(app, resources={r"/api/*": {
    "origins": ["http://localhost:3000", "http://localhost:3006"],
    "methods": ["GET", "POST", "OPTIONS"],
    "allow_headers": ["Content-Type"]
}})
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

# In-memory session store
sessions = {}


def emit_event(session_id: str, event_type: str, data: dict):
    """Push an SSE event to the session's queue."""
    if session_id in sessions:
        sessions[session_id]["events"].put({
            "event": event_type,
            "data": data
        })


def run_pipeline(session_id: str):
    """Main analysis pipeline. Runs in background thread."""
    session = sessions[session_id]

    try:
        # Phase 1: Parse PDFs
        emit_event(session_id, "parsing_status", {
            "stage": "protocol", "progress": 10, "message": "Parsing your protocol..."
        })
        protocol_text = parse_pdf(session["protocol_bytes"], session["protocol_name"])
        session["protocol_text"] = protocol_text

        emit_event(session_id, "parsing_status", {
            "stage": "paper", "progress": 50, "message": "Parsing research paper..."
        })
        paper_text = parse_pdf(session["paper_bytes"], session["paper_name"])
        session["paper_text"] = paper_text

        emit_event(session_id, "parsing_status", {
            "stage": "complete", "progress": 100, "message": "Parsing complete"
        })

        # Phase 2: Generate hypotheses (parallel)
        all_hypotheses = []

        for agent in AGENTS:
            emit_event(session_id, "agent_started", {
                "agent_id": agent["id"],
                "name": agent["name"],
                "domain": agent["domain"],
                "methodology": agent["methodology"],
                "personality": agent["personality"],
                "color": agent["color"],
                "description": agent["description"],
            })

        with ThreadPoolExecutor(max_workers=6) as executor:
            future_to_agent = {
                executor.submit(generate_hypotheses, agent, protocol_text, paper_text): agent
                for agent in AGENTS
            }

            for future in as_completed(future_to_agent):
                agent = future_to_agent[future]
                try:
                    hypotheses = future.result()
                    for h in hypotheses:
                        emit_event(session_id, "hypothesis_generated", {
                            "agent_id": agent["id"],
                            "hypothesis": h
                        })
                        all_hypotheses.append(h)

                    emit_event(session_id, "agent_complete", {
                        "agent_id": agent["id"],
                        "hypothesis_count": len(hypotheses)
                    })
                except Exception as e:
                    emit_event(session_id, "agent_complete", {
                        "agent_id": agent["id"],
                        "hypothesis_count": 0,
                        "error": str(e)
                    })

        # Store hypotheses in session
        session["hypotheses"] = {h["hypothesis_id"]: h for h in all_hypotheses}

        # Initialize ELO ratings
        elo_ratings = {h["hypothesis_id"]: 1200 for h in all_hypotheses}
        win_loss = {h["hypothesis_id"]: {"wins": 0, "losses": 0, "draws": 0} for h in all_hypotheses}

        # Phase 3: Tournament
        active_ids = [
            hid for hid in elo_ratings
            if hid not in session.get("rejected", set())
        ]
        matchups = generate_matchups(active_ids, rounds_per_hypothesis=4)

        emit_event(session_id, "tournament_started", {
            "total_hypotheses": len(active_ids),
            "total_matchups": len(matchups)
        })

        # Create short summaries for evaluator context
        protocol_summary = protocol_text[:3000]
        paper_summary = paper_text[:3000]

        for round_num, (id_a, id_b) in enumerate(matchups, 1):
            # Skip if either was rejected mid-tournament
            if id_a in session.get("rejected", set()) or id_b in session.get("rejected", set()):
                continue

            h_a = session["hypotheses"][id_a]
            h_b = session["hypotheses"][id_b]

            try:
                result = evaluate_matchup(h_a, h_b, protocol_summary, paper_summary)

                winner_id = None
                loser_id = None
                is_draw = result.get("winner") == "draw" or result.get("score") == "draw"

                if not is_draw:
                    if result.get("winner") == "a":
                        winner_id, loser_id = id_a, id_b
                    else:
                        winner_id, loser_id = id_b, id_a

                    new_winner, new_loser = calculate_elo(
                        elo_ratings[winner_id], elo_ratings[loser_id]
                    )
                    old_winner = elo_ratings[winner_id]
                    old_loser = elo_ratings[loser_id]
                    elo_ratings[winner_id] = new_winner
                    elo_ratings[loser_id] = new_loser
                    win_loss[winner_id]["wins"] += 1
                    win_loss[loser_id]["losses"] += 1
                else:
                    new_a, new_b = calculate_elo(
                        elo_ratings[id_a], elo_ratings[id_b], draw=True
                    )
                    old_winner = elo_ratings[id_a]
                    old_loser = elo_ratings[id_b]
                    elo_ratings[id_a] = new_a
                    elo_ratings[id_b] = new_b
                    win_loss[id_a]["draws"] += 1
                    win_loss[id_b]["draws"] += 1
                    winner_id = id_a  # For display purposes

                emit_event(session_id, "matchup_result", {
                    "round": round_num,
                    "total_rounds": len(matchups),
                    "hypothesis_a": {"id": id_a, "title": h_a["title"], "agent_name": h_a.get("agent_name"), "agent_color": h_a.get("agent_color")},
                    "hypothesis_b": {"id": id_b, "title": h_b["title"], "agent_name": h_b.get("agent_name"), "agent_color": h_b.get("agent_color")},
                    "winner": result.get("winner"),
                    "score": result.get("score", "narrow"),
                    "reasoning": result.get("reasoning", ""),
                    "criteria_scores": result.get("criteria_scores", {}),
                })

                # Send leaderboard update
                rankings = sorted(
                    [
                        {
                            "id": hid,
                            "title": session["hypotheses"][hid]["title"],
                            "agent_name": session["hypotheses"][hid].get("agent_name"),
                            "agent_color": session["hypotheses"][hid].get("agent_color"),
                            "elo": elo_ratings[hid],
                            "wins": win_loss[hid]["wins"],
                            "losses": win_loss[hid]["losses"],
                            "draws": win_loss[hid]["draws"],
                            "pinned": hid in session.get("pinned", set()),
                        }
                        for hid in elo_ratings
                        if hid not in session.get("rejected", set())
                    ],
                    key=lambda x: x["elo"],
                    reverse=True
                )
                emit_event(session_id, "leaderboard_update", {"rankings": rankings})

            except Exception as e:
                emit_event(session_id, "matchup_result", {
                    "round": round_num,
                    "total_rounds": len(matchups),
                    "error": str(e)
                })

        # Store final state
        for hid in session["hypotheses"]:
            session["hypotheses"][hid]["elo"] = elo_ratings.get(hid, 1200)
            session["hypotheses"][hid]["wins"] = win_loss.get(hid, {}).get("wins", 0)
            session["hypotheses"][hid]["losses"] = win_loss.get(hid, {}).get("losses", 0)

        # Final rankings
        final_rankings = sorted(
            [
                {**session["hypotheses"][hid], "elo": elo_ratings[hid]}
                for hid in elo_ratings
                if hid not in session.get("rejected", set())
            ],
            key=lambda x: x["elo"],
            reverse=True
        )

        session["final_rankings"] = final_rankings

        emit_event(session_id, "tournament_complete", {
            "final_rankings": [
                {"id": r["hypothesis_id"], "title": r["title"], "elo": r["elo"],
                 "agent_name": r.get("agent_name"), "wins": r.get("wins", 0), "losses": r.get("losses", 0)}
                for r in final_rankings[:10]
            ]
        })

    except Exception as e:
        emit_event(session_id, "error", {"message": str(e)})

    finally:
        # Signal stream end
        emit_event(session_id, "pipeline_complete", {})


@app.route('/api/co-researcher/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "co-researcher"})


@app.route('/api/co-researcher/analyze', methods=['POST'])
def analyze():
    if 'protocol' not in request.files or 'paper' not in request.files:
        return jsonify({"error": "Both 'protocol' and 'paper' PDF files are required"}), 400

    protocol_file = request.files['protocol']
    paper_file = request.files['paper']

    if not protocol_file.filename.lower().endswith('.pdf'):
        return jsonify({"error": "Protocol must be a PDF file"}), 400
    if not paper_file.filename.lower().endswith('.pdf'):
        return jsonify({"error": "Paper must be a PDF file"}), 400

    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "events": Queue(),
        "protocol_bytes": protocol_file.read(),
        "protocol_name": protocol_file.filename,
        "paper_bytes": paper_file.read(),
        "paper_name": paper_file.filename,
        "hypotheses": {},
        "pinned": set(),
        "rejected": set(),
        "protocol_text": "",
        "paper_text": "",
        "final_rankings": [],
    }

    # Start pipeline in background thread
    thread = threading.Thread(target=run_pipeline, args=(session_id,), daemon=True)
    thread.start()

    return jsonify({"session_id": session_id})


@app.route('/api/co-researcher/stream/<session_id>', methods=['GET'])
def stream(session_id):
    if session_id not in sessions:
        return jsonify({"error": "Session not found"}), 404

    def event_stream():
        while True:
            try:
                event = sessions[session_id]["events"].get(timeout=120)
                yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"

                if event["event"] == "pipeline_complete":
                    break
            except Empty:
                # Send keepalive
                yield ": keepalive\n\n"

    return Response(
        event_stream(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        }
    )


@app.route('/api/co-researcher/pin/<session_id>', methods=['POST'])
def pin_hypothesis(session_id):
    if session_id not in sessions:
        return jsonify({"error": "Session not found"}), 404

    data = request.get_json()
    hypothesis_id = data.get("hypothesis_id")
    if not hypothesis_id:
        return jsonify({"error": "hypothesis_id required"}), 400

    sessions[session_id]["pinned"].add(hypothesis_id)
    sessions[session_id]["rejected"].discard(hypothesis_id)
    return jsonify({"ok": True, "pinned": list(sessions[session_id]["pinned"])})


@app.route('/api/co-researcher/reject/<session_id>', methods=['POST'])
def reject_hypothesis(session_id):
    if session_id not in sessions:
        return jsonify({"error": "Session not found"}), 404

    data = request.get_json()
    hypothesis_id = data.get("hypothesis_id")
    if not hypothesis_id:
        return jsonify({"error": "hypothesis_id required"}), 400

    sessions[session_id]["rejected"].add(hypothesis_id)
    sessions[session_id]["pinned"].discard(hypothesis_id)
    return jsonify({"ok": True, "rejected": list(sessions[session_id]["rejected"])})


@app.route('/api/co-researcher/report/<session_id>', methods=['POST'])
def generate_report_endpoint(session_id):
    if session_id not in sessions:
        return jsonify({"error": "Session not found"}), 404

    session = sessions[session_id]
    rankings = session.get("final_rankings", [])
    pinned_ids = session.get("pinned", set())

    top_5 = rankings[:5]
    pinned = [session["hypotheses"][hid] for hid in pinned_ids if hid in session["hypotheses"]]

    report = generate_report(
        top_hypotheses=top_5,
        pinned_hypotheses=pinned,
        protocol_text=session.get("protocol_text", ""),
        paper_text=session.get("paper_text", ""),
        debate_history=[]
    )

    revised = generate_revised_protocol(
        top_hypotheses=top_5,
        protocol_text=session.get("protocol_text", "")
    )

    return jsonify({
        "report": report,
        "revised_protocol": revised
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5010, debug=True, threaded=True)
```

**Step 2: Test the full backend**

Run: `cd backend && python -m co_researcher.app`
Expected: Flask starts on 5010

Test health: `curl http://localhost:5010/api/co-researcher/health`
Expected: `{"status":"ok","service":"co-researcher"}`

**Step 3: Commit**

```bash
git add backend/co_researcher/app.py
git commit -m "feat(co-researcher): full pipeline with SSE streaming, pin/reject, report endpoints"
```

---

## Task 7: Frontend - Page Route + Upload Panel (Phase 1)

**Files:**
- Create: `frontend/app/co-researcher/page.tsx`
- Create: `frontend/components/co-researcher/UploadPanel.tsx`

**Step 1: Create the main page component**

This page is standalone (no sidebar, no auth). It manages the 4-phase state machine and passes data down to phase components.

```tsx
// frontend/app/co-researcher/page.tsx
'use client'

import React, { useState, useRef, useCallback } from 'react'
import UploadPanel from '@/components/co-researcher/UploadPanel'

const API_BASE = 'http://localhost:5010/api/co-researcher'

type Phase = 'upload' | 'generating' | 'tournament' | 'results'

// Types shared across components
export interface Hypothesis {
  hypothesis_id: string
  title: string
  integration_type: string
  evidence: string
  risk_level: string
  protocol_sections_affected: string[]
  implementation_steps: string[]
  confidence: number
  agent_id: string
  agent_name: string
  agent_domain: string
  agent_personality: string
  agent_color: string
  elo?: number
  wins?: number
  losses?: number
  draws?: number
}

export interface Agent {
  agent_id: string
  name: string
  domain: string
  methodology: string
  personality: string
  color: string
  description: string
  hypotheses: Hypothesis[]
  complete: boolean
  error?: string
}

export interface MatchupResult {
  round: number
  total_rounds: number
  hypothesis_a: { id: string; title: string; agent_name: string; agent_color: string }
  hypothesis_b: { id: string; title: string; agent_name: string; agent_color: string }
  winner: string
  score: string
  reasoning: string
  criteria_scores: any
}

export interface RankingEntry {
  id: string
  title: string
  agent_name: string
  agent_color: string
  elo: number
  wins: number
  losses: number
  draws: number
  pinned: boolean
}

export default function CoResearcherPage() {
  const [phase, setPhase] = useState<Phase>('upload')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [agents, setAgents] = useState<Record<string, Agent>>({})
  const [matchups, setMatchups] = useState<MatchupResult[]>([])
  const [currentMatchup, setCurrentMatchup] = useState<MatchupResult | null>(null)
  const [rankings, setRankings] = useState<RankingEntry[]>([])
  const [pinned, setPinned] = useState<Set<string>>(new Set())
  const [rejected, setRejected] = useState<Set<string>>(new Set())
  const [parseProgress, setParseProgress] = useState({ progress: 0, message: '' })
  const [tournamentInfo, setTournamentInfo] = useState({ total: 0, current: 0 })
  const [finalRankings, setFinalRankings] = useState<any[]>([])
  const [report, setReport] = useState<any>(null)
  const [revisedProtocol, setRevisedProtocol] = useState<string>('')
  const [isGeneratingReport, setIsGeneratingReport] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleUpload = useCallback(async (protocolFile: File, paperFile: File) => {
    setError(null)
    const formData = new FormData()
    formData.append('protocol', protocolFile)
    formData.append('paper', paperFile)

    try {
      const resp = await fetch(`${API_BASE}/analyze`, {
        method: 'POST',
        body: formData,
      })
      if (!resp.ok) {
        const err = await resp.json()
        throw new Error(err.error || 'Upload failed')
      }
      const { session_id } = await resp.json()
      setSessionId(session_id)
      setPhase('generating')

      // Start SSE stream
      startStream(session_id)
    } catch (e: any) {
      setError(e.message)
    }
  }, [])

  const startStream = (sid: string) => {
    const eventSource = new EventSource(`${API_BASE}/stream/${sid}`)

    eventSource.addEventListener('parsing_status', (e) => {
      const data = JSON.parse(e.data)
      setParseProgress({ progress: data.progress, message: data.message })
    })

    eventSource.addEventListener('agent_started', (e) => {
      const data = JSON.parse(e.data)
      setAgents(prev => ({
        ...prev,
        [data.agent_id]: {
          ...data,
          hypotheses: [],
          complete: false,
        }
      }))
    })

    eventSource.addEventListener('hypothesis_generated', (e) => {
      const data = JSON.parse(e.data)
      setAgents(prev => ({
        ...prev,
        [data.agent_id]: {
          ...prev[data.agent_id],
          hypotheses: [...(prev[data.agent_id]?.hypotheses || []), data.hypothesis],
        }
      }))
    })

    eventSource.addEventListener('agent_complete', (e) => {
      const data = JSON.parse(e.data)
      setAgents(prev => ({
        ...prev,
        [data.agent_id]: {
          ...prev[data.agent_id],
          complete: true,
          error: data.error,
        }
      }))
    })

    eventSource.addEventListener('tournament_started', (e) => {
      const data = JSON.parse(e.data)
      setTournamentInfo({ total: data.total_matchups, current: 0 })
      setPhase('tournament')
    })

    eventSource.addEventListener('matchup_result', (e) => {
      const data = JSON.parse(e.data)
      setCurrentMatchup(data)
      setMatchups(prev => [...prev, data])
      setTournamentInfo(prev => ({ ...prev, current: data.round }))
    })

    eventSource.addEventListener('leaderboard_update', (e) => {
      const data = JSON.parse(e.data)
      setRankings(data.rankings)
    })

    eventSource.addEventListener('tournament_complete', (e) => {
      const data = JSON.parse(e.data)
      setFinalRankings(data.final_rankings)
      setPhase('results')
    })

    eventSource.addEventListener('error', (e) => {
      // SSE error event (connection issue)
      if (eventSource.readyState === EventSource.CLOSED) {
        return
      }
      try {
        const data = JSON.parse((e as any).data)
        setError(data.message)
      } catch {
        // Connection error, not a data error
      }
    })

    eventSource.addEventListener('pipeline_complete', () => {
      eventSource.close()
    })
  }

  const handlePin = async (hypothesisId: string) => {
    if (!sessionId) return
    setPinned(prev => new Set([...prev, hypothesisId]))
    setRejected(prev => { const next = new Set(prev); next.delete(hypothesisId); return next })
    await fetch(`${API_BASE}/pin/${sessionId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hypothesis_id: hypothesisId }),
    })
  }

  const handleReject = async (hypothesisId: string) => {
    if (!sessionId) return
    setRejected(prev => new Set([...prev, hypothesisId]))
    setPinned(prev => { const next = new Set(prev); next.delete(hypothesisId); return next })
    await fetch(`${API_BASE}/reject/${sessionId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ hypothesis_id: hypothesisId }),
    })
  }

  const handleGenerateReport = async () => {
    if (!sessionId) return
    setIsGeneratingReport(true)
    try {
      const resp = await fetch(`${API_BASE}/report/${sessionId}`, { method: 'POST' })
      const data = await resp.json()
      setReport(data.report)
      setRevisedProtocol(data.revised_protocol)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setIsGeneratingReport(false)
    }
  }

  const handleReset = () => {
    setPhase('upload')
    setSessionId(null)
    setAgents({})
    setMatchups([])
    setCurrentMatchup(null)
    setRankings([])
    setPinned(new Set())
    setRejected(new Set())
    setParseProgress({ progress: 0, message: '' })
    setTournamentInfo({ total: 0, current: 0 })
    setFinalRankings([])
    setReport(null)
    setRevisedProtocol('')
    setError(null)
  }

  return (
    <div style={{ minHeight: '100vh', background: '#0F0F12' }}>
      {/* Header */}
      <div style={{
        padding: '20px 40px',
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10,
            background: 'linear-gradient(135deg, #6366F1, #8B5CF6)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 18,
          }}>
            C
          </div>
          <div>
            <div style={{ color: '#fff', fontSize: 18, fontWeight: 600, letterSpacing: '-0.02em' }}>
              Co-Researcher
            </div>
            <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: 12 }}>
              AI-Powered Protocol Integration Engine
            </div>
          </div>
        </div>
        {phase !== 'upload' && (
          <button
            onClick={handleReset}
            style={{
              padding: '8px 16px', borderRadius: 8,
              background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)',
              color: 'rgba(255,255,255,0.6)', fontSize: 13, cursor: 'pointer',
            }}
          >
            New Analysis
          </button>
        )}
      </div>

      {/* Error banner */}
      {error && (
        <div style={{
          margin: '16px 40px', padding: '12px 16px', borderRadius: 8,
          background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)',
          color: '#EF4444', fontSize: 13,
        }}>
          {error}
        </div>
      )}

      {/* Phase content */}
      <div style={{ padding: '40px' }}>
        {phase === 'upload' && (
          <UploadPanel onUpload={handleUpload} />
        )}

        {phase === 'generating' && (
          <div>
            {/* Parsing progress */}
            {parseProgress.progress < 100 && (
              <div style={{ marginBottom: 32 }}>
                <div style={{ color: 'rgba(255,255,255,0.6)', fontSize: 14, marginBottom: 8 }}>
                  {parseProgress.message}
                </div>
                <div style={{ height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 2 }}>
                  <div style={{
                    height: '100%', borderRadius: 2, transition: 'width 0.5s',
                    background: 'linear-gradient(90deg, #6366F1, #8B5CF6)',
                    width: `${parseProgress.progress}%`,
                  }} />
                </div>
              </div>
            )}

            {/* Agent cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(350px, 1fr))', gap: 16 }}>
              {Object.values(agents).map(agent => (
                <div key={agent.agent_id} style={{
                  padding: 20, borderRadius: 12,
                  background: 'rgba(255,255,255,0.03)',
                  border: `1px solid ${agent.complete ? agent.color + '40' : 'rgba(255,255,255,0.06)'}`,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                    <div style={{
                      width: 10, height: 10, borderRadius: '50%',
                      background: agent.complete ? agent.color : 'rgba(255,255,255,0.2)',
                      boxShadow: agent.complete ? `0 0 8px ${agent.color}60` : 'none',
                    }} />
                    <div style={{ color: '#fff', fontWeight: 600, fontSize: 15 }}>
                      Agent {agent.name}
                    </div>
                    <div style={{ color: 'rgba(255,255,255,0.3)', fontSize: 12, marginLeft: 'auto' }}>
                      {agent.personality} / {agent.domain}
                    </div>
                  </div>
                  {!agent.complete && agent.hypotheses.length === 0 && (
                    <div style={{ color: 'rgba(255,255,255,0.3)', fontSize: 13 }}>
                      Generating hypotheses...
                    </div>
                  )}
                  {agent.error && (
                    <div style={{ color: '#EF4444', fontSize: 13 }}>Error: {agent.error}</div>
                  )}
                  {agent.hypotheses.map((h, i) => (
                    <div key={i} style={{
                      padding: '8px 12px', marginBottom: 6, borderRadius: 8,
                      background: 'rgba(255,255,255,0.04)', fontSize: 13,
                      color: 'rgba(255,255,255,0.7)',
                    }}>
                      {h.title}
                    </div>
                  ))}
                  {agent.complete && (
                    <div style={{ color: agent.color, fontSize: 12, marginTop: 8 }}>
                      {agent.hypotheses.length} hypotheses generated
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {phase === 'tournament' && (
          <div>
            {/* Tournament header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 24 }}>
              <div style={{ color: '#fff', fontSize: 20, fontWeight: 600 }}>
                Tournament
              </div>
              <div style={{
                padding: '4px 12px', borderRadius: 20,
                background: 'rgba(99,102,241,0.15)', color: '#818CF8', fontSize: 13,
              }}>
                Round {tournamentInfo.current} / {tournamentInfo.total}
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 24 }}>
              {/* Current matchup */}
              <div>
                {currentMatchup && (
                  <div style={{
                    padding: 24, borderRadius: 16,
                    background: 'rgba(255,255,255,0.03)',
                    border: '1px solid rgba(255,255,255,0.08)',
                    marginBottom: 16,
                  }}>
                    <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.3)', marginBottom: 16, textTransform: 'uppercase', letterSpacing: '0.1em' }}>
                      Current Matchup
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: 16, alignItems: 'start' }}>
                      {/* Hypothesis A */}
                      <div style={{
                        padding: 16, borderRadius: 12,
                        background: currentMatchup.winner === 'a' ? 'rgba(16,185,129,0.08)' : 'rgba(255,255,255,0.03)',
                        border: `1px solid ${currentMatchup.winner === 'a' ? 'rgba(16,185,129,0.3)' : 'rgba(255,255,255,0.06)'}`,
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                          <div style={{ width: 8, height: 8, borderRadius: '50%', background: currentMatchup.hypothesis_a.agent_color }} />
                          <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: 12 }}>{currentMatchup.hypothesis_a.agent_name}</span>
                          {currentMatchup.winner === 'a' && <span style={{ color: '#10B981', fontSize: 11, marginLeft: 'auto' }}>WINNER</span>}
                        </div>
                        <div style={{ color: '#fff', fontSize: 14 }}>{currentMatchup.hypothesis_a.title}</div>
                      </div>

                      {/* VS */}
                      <div style={{
                        color: 'rgba(255,255,255,0.2)', fontSize: 14, fontWeight: 700,
                        alignSelf: 'center', padding: '0 8px',
                      }}>
                        VS
                      </div>

                      {/* Hypothesis B */}
                      <div style={{
                        padding: 16, borderRadius: 12,
                        background: currentMatchup.winner === 'b' ? 'rgba(16,185,129,0.08)' : 'rgba(255,255,255,0.03)',
                        border: `1px solid ${currentMatchup.winner === 'b' ? 'rgba(16,185,129,0.3)' : 'rgba(255,255,255,0.06)'}`,
                      }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                          <div style={{ width: 8, height: 8, borderRadius: '50%', background: currentMatchup.hypothesis_b.agent_color }} />
                          <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: 12 }}>{currentMatchup.hypothesis_b.agent_name}</span>
                          {currentMatchup.winner === 'b' && <span style={{ color: '#10B981', fontSize: 11, marginLeft: 'auto' }}>WINNER</span>}
                        </div>
                        <div style={{ color: '#fff', fontSize: 14 }}>{currentMatchup.hypothesis_b.title}</div>
                      </div>
                    </div>

                    {/* Evaluator reasoning */}
                    {currentMatchup.reasoning && (
                      <div style={{
                        marginTop: 16, padding: 12, borderRadius: 8,
                        background: 'rgba(99,102,241,0.06)',
                        border: '1px solid rgba(99,102,241,0.15)',
                      }}>
                        <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: 11, marginBottom: 4, textTransform: 'uppercase' }}>
                          Evaluator Reasoning
                        </div>
                        <div style={{ color: 'rgba(255,255,255,0.7)', fontSize: 13, lineHeight: 1.5 }}>
                          {currentMatchup.reasoning}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Pinned / Rejected controls */}
                <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                  {rankings.slice(0, 8).map(r => (
                    <div key={r.id} style={{
                      display: 'flex', alignItems: 'center', gap: 8,
                      padding: '6px 12px', borderRadius: 8,
                      background: pinned.has(r.id) ? 'rgba(16,185,129,0.1)' : rejected.has(r.id) ? 'rgba(239,68,68,0.1)' : 'rgba(255,255,255,0.03)',
                      border: `1px solid ${pinned.has(r.id) ? 'rgba(16,185,129,0.3)' : rejected.has(r.id) ? 'rgba(239,68,68,0.3)' : 'rgba(255,255,255,0.06)'}`,
                      fontSize: 12, color: 'rgba(255,255,255,0.6)',
                    }}>
                      <span style={{ maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {r.title}
                      </span>
                      <button
                        onClick={() => handlePin(r.id)}
                        style={{
                          background: 'none', border: 'none', cursor: 'pointer', fontSize: 14,
                          color: pinned.has(r.id) ? '#10B981' : 'rgba(255,255,255,0.3)',
                        }}
                        title="Pin"
                      >
                        P
                      </button>
                      <button
                        onClick={() => handleReject(r.id)}
                        style={{
                          background: 'none', border: 'none', cursor: 'pointer', fontSize: 14,
                          color: rejected.has(r.id) ? '#EF4444' : 'rgba(255,255,255,0.3)',
                        }}
                        title="Reject"
                      >
                        X
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* ELO Leaderboard */}
              <div style={{
                padding: 20, borderRadius: 12,
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.06)',
                height: 'fit-content',
              }}>
                <div style={{ color: '#fff', fontWeight: 600, fontSize: 14, marginBottom: 16 }}>
                  ELO Leaderboard
                </div>
                {rankings.map((r, i) => (
                  <div key={r.id} style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '8px 0',
                    borderBottom: i < rankings.length - 1 ? '1px solid rgba(255,255,255,0.04)' : 'none',
                  }}>
                    <span style={{ color: 'rgba(255,255,255,0.3)', fontSize: 12, width: 20 }}>{i + 1}</span>
                    <div style={{ width: 8, height: 8, borderRadius: '50%', background: r.agent_color }} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{
                        color: 'rgba(255,255,255,0.8)', fontSize: 12,
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                      }}>
                        {r.title}
                      </div>
                      <div style={{ color: 'rgba(255,255,255,0.3)', fontSize: 11 }}>
                        {r.agent_name} | {r.wins}W-{r.losses}L
                      </div>
                    </div>
                    <span style={{
                      color: r.elo > 1200 ? '#10B981' : r.elo < 1200 ? '#EF4444' : 'rgba(255,255,255,0.4)',
                      fontSize: 13, fontWeight: 600, fontFamily: 'monospace',
                    }}>
                      {r.elo}
                    </span>
                    {r.pinned && <span style={{ color: '#10B981', fontSize: 10 }}>PIN</span>}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {phase === 'results' && (
          <div>
            <div style={{ color: '#fff', fontSize: 24, fontWeight: 600, marginBottom: 8 }}>
              Results
            </div>
            <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: 14, marginBottom: 32 }}>
              Top integration recommendations ranked by ELO tournament
            </div>

            {/* Top ranked hypotheses */}
            <div style={{ display: 'grid', gap: 16, marginBottom: 32 }}>
              {finalRankings.map((r: any, i: number) => (
                <div key={r.id} style={{
                  padding: 24, borderRadius: 12,
                  background: 'rgba(255,255,255,0.03)',
                  border: `1px solid ${i === 0 ? 'rgba(99,102,241,0.3)' : 'rgba(255,255,255,0.06)'}`,
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 12 }}>
                    <div style={{
                      width: 28, height: 28, borderRadius: 8,
                      background: i === 0 ? 'rgba(99,102,241,0.2)' : 'rgba(255,255,255,0.06)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      color: i === 0 ? '#818CF8' : 'rgba(255,255,255,0.4)', fontSize: 13, fontWeight: 700,
                    }}>
                      {i + 1}
                    </div>
                    <div style={{ color: '#fff', fontSize: 16, fontWeight: 500, flex: 1 }}>
                      {r.title}
                    </div>
                    <div style={{
                      padding: '4px 10px', borderRadius: 6,
                      background: 'rgba(255,255,255,0.06)',
                      color: 'rgba(255,255,255,0.5)', fontSize: 13, fontFamily: 'monospace',
                    }}>
                      ELO {r.elo}
                    </div>
                  </div>
                  <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: 12, marginBottom: 4 }}>
                    Agent {r.agent_name} | {r.wins}W-{r.losses}L
                  </div>
                </div>
              ))}
            </div>

            {/* Report generation */}
            {!report && (
              <button
                onClick={handleGenerateReport}
                disabled={isGeneratingReport}
                style={{
                  padding: '12px 24px', borderRadius: 10,
                  background: isGeneratingReport ? 'rgba(99,102,241,0.3)' : 'linear-gradient(135deg, #6366F1, #8B5CF6)',
                  border: 'none', color: '#fff', fontSize: 14, fontWeight: 500,
                  cursor: isGeneratingReport ? 'not-allowed' : 'pointer',
                }}
              >
                {isGeneratingReport ? 'Generating Report...' : 'Generate Integration Report & Revised Protocol'}
              </button>
            )}

            {report && (
              <div style={{ marginTop: 32 }}>
                <div style={{ color: '#fff', fontSize: 18, fontWeight: 600, marginBottom: 16 }}>
                  Integration Report
                </div>
                <div style={{
                  padding: 24, borderRadius: 12,
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px solid rgba(255,255,255,0.06)',
                  color: 'rgba(255,255,255,0.7)', fontSize: 14, lineHeight: 1.7,
                  whiteSpace: 'pre-wrap',
                }}>
                  {report.report_markdown}
                </div>
              </div>
            )}

            {revisedProtocol && (
              <div style={{ marginTop: 32 }}>
                <div style={{ color: '#fff', fontSize: 18, fontWeight: 600, marginBottom: 16 }}>
                  Revised Protocol
                </div>
                <div style={{
                  padding: 24, borderRadius: 12,
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px solid rgba(255,255,255,0.06)',
                  color: 'rgba(255,255,255,0.7)', fontSize: 14, lineHeight: 1.7,
                  whiteSpace: 'pre-wrap',
                }}>
                  {revisedProtocol}
                </div>
              </div>
            )}

            {/* Reset */}
            <button
              onClick={handleReset}
              style={{
                marginTop: 24, padding: '10px 20px', borderRadius: 8,
                background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)',
                color: 'rgba(255,255,255,0.6)', fontSize: 13, cursor: 'pointer',
              }}
            >
              Start New Analysis
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
```

**Step 2: Create the UploadPanel component**

```tsx
// frontend/components/co-researcher/UploadPanel.tsx
'use client'

import React, { useState, useRef } from 'react'

interface UploadPanelProps {
  onUpload: (protocol: File, paper: File) => void
}

export default function UploadPanel({ onUpload }: UploadPanelProps) {
  const [protocolFile, setProtocolFile] = useState<File | null>(null)
  const [paperFile, setPaperFile] = useState<File | null>(null)
  const [isUploading, setIsUploading] = useState(false)
  const protocolRef = useRef<HTMLInputElement>(null)
  const paperRef = useRef<HTMLInputElement>(null)

  const handleDrop = (setter: (f: File) => void) => (e: React.DragEvent) => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file && file.name.toLowerCase().endsWith('.pdf')) {
      setter(file)
    }
  }

  const handleSubmit = async () => {
    if (!protocolFile || !paperFile) return
    setIsUploading(true)
    onUpload(protocolFile, paperFile)
  }

  const dropZoneStyle = (hasFile: boolean): React.CSSProperties => ({
    flex: 1,
    minHeight: 220,
    borderRadius: 16,
    border: `2px dashed ${hasFile ? 'rgba(99,102,241,0.4)' : 'rgba(255,255,255,0.1)'}`,
    background: hasFile ? 'rgba(99,102,241,0.04)' : 'rgba(255,255,255,0.02)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    transition: 'all 0.2s',
    padding: 32,
  })

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      <div style={{ textAlign: 'center', marginBottom: 48 }}>
        <div style={{
          color: '#fff', fontSize: 32, fontWeight: 700,
          letterSpacing: '-0.03em', marginBottom: 12,
        }}>
          Integrate Research Into Your Protocol
        </div>
        <div style={{ color: 'rgba(255,255,255,0.4)', fontSize: 16, maxWidth: 600, margin: '0 auto' }}>
          Upload your protocol and a research paper. Our 6 specialist AI agents will generate
          and debate integration hypotheses in a live tournament.
        </div>
      </div>

      <div style={{ display: 'flex', gap: 24, marginBottom: 32 }}>
        {/* Protocol upload */}
        <div
          style={dropZoneStyle(!!protocolFile)}
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop(setProtocolFile)}
          onClick={() => protocolRef.current?.click()}
        >
          <input
            ref={protocolRef}
            type="file"
            accept=".pdf"
            style={{ display: 'none' }}
            onChange={(e) => e.target.files?.[0] && setProtocolFile(e.target.files[0])}
          />
          <div style={{
            width: 48, height: 48, borderRadius: 12,
            background: protocolFile ? 'rgba(99,102,241,0.15)' : 'rgba(255,255,255,0.06)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            marginBottom: 16, fontSize: 20,
            color: protocolFile ? '#818CF8' : 'rgba(255,255,255,0.3)',
          }}>
            {protocolFile ? 'P' : '+'}
          </div>
          <div style={{ color: '#fff', fontSize: 15, fontWeight: 500, marginBottom: 4 }}>
            Your Protocol
          </div>
          {protocolFile ? (
            <div style={{ color: '#818CF8', fontSize: 13 }}>{protocolFile.name}</div>
          ) : (
            <div style={{ color: 'rgba(255,255,255,0.3)', fontSize: 13 }}>
              Drop PDF here or click to browse
            </div>
          )}
        </div>

        {/* Paper upload */}
        <div
          style={dropZoneStyle(!!paperFile)}
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop(setPaperFile)}
          onClick={() => paperRef.current?.click()}
        >
          <input
            ref={paperRef}
            type="file"
            accept=".pdf"
            style={{ display: 'none' }}
            onChange={(e) => e.target.files?.[0] && setPaperFile(e.target.files[0])}
          />
          <div style={{
            width: 48, height: 48, borderRadius: 12,
            background: paperFile ? 'rgba(99,102,241,0.15)' : 'rgba(255,255,255,0.06)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            marginBottom: 16, fontSize: 20,
            color: paperFile ? '#818CF8' : 'rgba(255,255,255,0.3)',
          }}>
            {paperFile ? 'R' : '+'}
          </div>
          <div style={{ color: '#fff', fontSize: 15, fontWeight: 500, marginBottom: 4 }}>
            Research Paper
          </div>
          {paperFile ? (
            <div style={{ color: '#818CF8', fontSize: 13 }}>{paperFile.name}</div>
          ) : (
            <div style={{ color: 'rgba(255,255,255,0.3)', fontSize: 13 }}>
              Drop PDF here or click to browse
            </div>
          )}
        </div>
      </div>

      <div style={{ textAlign: 'center' }}>
        <button
          onClick={handleSubmit}
          disabled={!protocolFile || !paperFile || isUploading}
          style={{
            padding: '14px 36px',
            borderRadius: 12,
            background: protocolFile && paperFile && !isUploading
              ? 'linear-gradient(135deg, #6366F1, #8B5CF6)'
              : 'rgba(255,255,255,0.06)',
            border: 'none',
            color: protocolFile && paperFile ? '#fff' : 'rgba(255,255,255,0.3)',
            fontSize: 15,
            fontWeight: 500,
            cursor: protocolFile && paperFile && !isUploading ? 'pointer' : 'not-allowed',
            transition: 'all 0.2s',
          }}
        >
          {isUploading ? 'Starting Analysis...' : 'Analyze & Generate Hypotheses'}
        </button>
      </div>
    </div>
  )
}
```

**Step 3: Test the frontend page loads**

Run: `cd frontend && npm run dev -- -p 3000`
Navigate to: `http://localhost:3000/co-researcher`
Expected: Dark-themed upload page with two drop zones

**Step 4: Commit**

```bash
git add frontend/app/co-researcher/page.tsx frontend/components/co-researcher/UploadPanel.tsx
git commit -m "feat(co-researcher): frontend page with upload panel + full 4-phase state machine"
```

---

## Task 8: Integration Test - Full End-to-End Flow

**Step 1: Start both servers**

Terminal 1:
```bash
cd backend && AZURE_OPENAI_API_KEY=your-key python -m co_researcher.app
```

Terminal 2:
```bash
cd frontend && npm run dev -- -p 3000
```

**Step 2: Test the flow**

1. Navigate to `http://localhost:3000/co-researcher`
2. Upload two PDFs (any research protocol + any research paper)
3. Click "Analyze & Generate Hypotheses"
4. Watch Phase 2: Agent cards should appear and populate with hypotheses
5. Watch Phase 3: Tournament matchups should stream, ELO leaderboard should update
6. Phase 4: Results should display with ranked hypotheses
7. Click "Generate Integration Report" and verify report + revised protocol appear

**Step 3: Fix any issues found during testing**

Debug common issues:
- CORS errors: Check Flask CORS config allows localhost:3000
- SSE connection drops: Check Flask `threaded=True` is set
- LlamaParse timeout: Check API key is valid, increase timeout
- Azure OpenAI 429s: Add retry logic or reduce parallel agents to 3

**Step 4: Commit fixes**

```bash
git add -A
git commit -m "fix(co-researcher): integration test fixes"
```

---

## Task 9: Polish - UI Refinements

**Files:**
- Modify: `frontend/app/co-researcher/page.tsx`

**Step 1: Add tournament progress bar to Phase 3**

In the tournament section, add a progress bar showing matchup completion:
```tsx
{/* Add after the tournament header div */}
<div style={{ height: 3, background: 'rgba(255,255,255,0.06)', borderRadius: 2, marginBottom: 24 }}>
  <div style={{
    height: '100%', borderRadius: 2, transition: 'width 0.3s',
    background: 'linear-gradient(90deg, #6366F1, #8B5CF6)',
    width: `${(tournamentInfo.current / Math.max(tournamentInfo.total, 1)) * 100}%`,
  }} />
</div>
```

**Step 2: Add "Skip to Results" button in tournament phase**

```tsx
<button
  onClick={() => setPhase('results')}
  style={{
    marginTop: 16, padding: '8px 16px', borderRadius: 8,
    background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)',
    color: 'rgba(255,255,255,0.4)', fontSize: 12, cursor: 'pointer',
  }}
>
  Skip to Results
</button>
```

**Step 3: Add matchup history (collapsible) below current matchup**

Show the last 5 matchup results in a compact view below the current matchup card.

**Step 4: Commit**

```bash
git add frontend/app/co-researcher/page.tsx
git commit -m "feat(co-researcher): tournament progress bar, skip button, matchup history"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | Flask skeleton + health | `backend/co_researcher/app.py`, `__init__.py` |
| 2 | LlamaParse parser | `backend/co_researcher/parser.py` |
| 3 | 6 agent definitions + generation | `backend/co_researcher/agents.py` |
| 4 | ELO tournament engine | `backend/co_researcher/tournament.py` |
| 5 | Report generator | `backend/co_researcher/report_generator.py` |
| 6 | Full pipeline with SSE | `backend/co_researcher/app.py` (rewrite) |
| 7 | Frontend page + all 4 phases | `frontend/app/co-researcher/page.tsx`, `UploadPanel.tsx` |
| 8 | Integration test | Manual E2E testing |
| 9 | UI polish | `frontend/app/co-researcher/page.tsx` |

**Total new files**: 7 backend + 2 frontend = 9 files
**No existing files modified** (this is an entirely additive feature)
