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

        protocol_summary = protocol_text[:3000]
        paper_summary = paper_text[:3000]

        for round_num, (id_a, id_b) in enumerate(matchups, 1):
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
                    elo_ratings[winner_id] = new_winner
                    elo_ratings[loser_id] = new_loser
                    win_loss[winner_id]["wins"] += 1
                    win_loss[loser_id]["losses"] += 1
                else:
                    new_a, new_b = calculate_elo(
                        elo_ratings[id_a], elo_ratings[id_b], draw=True
                    )
                    elo_ratings[id_a] = new_a
                    elo_ratings[id_b] = new_b
                    win_loss[id_a]["draws"] += 1
                    win_loss[id_b]["draws"] += 1

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
