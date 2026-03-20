"""
Research Translator — Flask API + Pipeline Orchestration

Endpoints:
  POST /api/co-researcher/analyze    — Upload "my research" + "papers I read", starts pipeline
  GET  /api/co-researcher/stream/<id> — SSE event stream
  POST /api/co-researcher/chat/<id>   — Interactive refinement chat
  GET  /api/co-researcher/health      — Health check
"""

import os
import sys

# Load .env file BEFORE any other imports that use env vars
from dotenv import load_dotenv
# Go up one level from co_researcher/ to backend/ to find .env
env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(env_path)

import uuid
import json
import threading
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor, as_completed

from flask import Flask, request, jsonify, Response
from flask_cors import CORS

from co_researcher.parser import parse_document
from co_researcher.decomposer import extract_context, decompose_layers
from co_researcher.translator import translate_insight
from co_researcher.adversarial import run_adversarial
from co_researcher.chat import build_chat_context, handle_chat_message

app = Flask(__name__)
CORS(app, resources={r"/api/*": {
    "origins": ["http://localhost:3000", "http://localhost:3001", "http://localhost:3006", "http://localhost:3009"],
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
            "data": data,
        })


def run_pipeline(session_id: str):
    """Main analysis pipeline. Runs in background thread."""
    session = sessions[session_id]

    try:
        papers = session["papers"]
        total_papers = len(papers)

        # ── Phase 1: Parse all documents ──
        emit_event(session_id, "parsing_status", {
            "stage": "target", "progress": 5,
            "message": "Parsing your research document..."
        })
        target_text = parse_document(session["target_bytes"], session["target_name"])
        session["target_text"] = target_text

        emit_event(session_id, "parsing_status", {
            "stage": "target", "progress": 20,
            "message": "Your research parsed. Parsing source papers..."
        })

        source_texts = []
        for i, paper in enumerate(papers):
            pct = 20 + int((i + 1) / total_papers * 30)
            emit_event(session_id, "parsing_status", {
                "stage": "source", "progress": pct,
                "paper_index": i,
                "message": f"Parsing paper {i+1}/{total_papers}: {paper['name']}..."
            })
            text = parse_document(paper["bytes"], paper["name"])
            source_texts.append(text)

        session["source_texts"] = source_texts
        emit_event(session_id, "parsing_status", {
            "stage": "complete", "progress": 50,
            "message": "All documents parsed."
        })

        # ── Phase 2: Context extraction + decomposition ──
        emit_event(session_id, "context_extracting", {
            "message": "Extracting structured context from your research..."
        })
        target_context = extract_context(target_text, "target")
        session["target_context"] = target_context

        emit_event(session_id, "context_extracted", {
            "role": "target",
            "context": target_context,
        })

        source_contexts = []
        all_decompositions = []

        for i, (paper, text) in enumerate(zip(papers, source_texts)):
            emit_event(session_id, "context_extracting", {
                "paper_index": i,
                "paper_name": paper["name"],
                "message": f"Extracting context from paper {i+1}: {paper['name']}..."
            })
            source_ctx = extract_context(text, "source")
            source_contexts.append(source_ctx)

            emit_event(session_id, "context_extracted", {
                "role": "source",
                "paper_index": i,
                "paper_name": paper["name"],
                "context": source_ctx,
            })

            # Decompose key methods + findings into abstraction layers
            items_to_decompose = (
                source_ctx.get("key_methods", [])[:3] +
                source_ctx.get("key_findings", [])[:2]
            )

            emit_event(session_id, "decomposition_started", {
                "paper_index": i,
                "paper_name": paper["name"],
                "item_count": len(items_to_decompose),
            })

            for j, item in enumerate(items_to_decompose):
                layers = decompose_layers(source_ctx, item)
                decomposition = {
                    "paper_index": i,
                    "paper_name": paper["name"],
                    "item": item,
                    "layers": layers,
                }
                all_decompositions.append(decomposition)

                emit_event(session_id, "layer_extracted", {
                    "paper_index": i,
                    "paper_name": paper["name"],
                    "item_index": j,
                    "item_name": item.get("name", item.get("finding", "Unknown")),
                    "layers": layers,
                })

        session["source_contexts"] = source_contexts
        session["decompositions"] = all_decompositions

        emit_event(session_id, "decomposition_complete", {
            "total_decompositions": len(all_decompositions),
        })

        # ── Phase 3: Translation attempts ──
        emit_event(session_id, "translation_started", {
            "total": len(all_decompositions),
            "message": "Translating insights into your research domain..."
        })

        translations = []
        for idx, decomp in enumerate(all_decompositions):
            paper_idx = decomp["paper_index"]
            source_ctx = source_contexts[paper_idx]

            emit_event(session_id, "translating_insight", {
                "index": idx,
                "total": len(all_decompositions),
                "paper_name": decomp["paper_name"],
                "item_name": decomp["item"].get("name", decomp["item"].get("finding", "Unknown")),
            })

            translation = translate_insight(source_ctx, target_context, decomp["layers"])
            translation["paper_index"] = paper_idx
            translation["paper_name"] = decomp["paper_name"]
            translation["translation_index"] = idx
            translations.append(translation)

            emit_event(session_id, "translation_complete", {
                "index": idx,
                "translation": translation,
            })

        session["translations"] = translations

        # ── Phase 4: Adversarial stress-test ──
        emit_event(session_id, "adversarial_started", {
            "total_translations": len(translations),
            "message": "Stress-testing each translation..."
        })

        adversarial_results = []

        # Run adversarial tests — one translation at a time to avoid rate limits,
        # but 4 agents in parallel per translation
        for idx, translation in enumerate(translations):
            paper_idx = translation["paper_index"]
            source_ctx = source_contexts[paper_idx]

            emit_event(session_id, "adversarial_testing", {
                "translation_index": idx,
                "title": translation.get("title", ""),
                "message": f"Stress-testing translation {idx+1}/{len(translations)}..."
            })

            result = run_adversarial(translation, source_ctx, target_context)
            result["translation_index"] = idx
            adversarial_results.append(result)

            # Emit each verdict as it completes
            for verdict in result.get("verdicts", []):
                emit_event(session_id, "agent_verdict", {
                    "translation_index": idx,
                    "translation_title": translation.get("title", ""),
                    "agent_id": verdict.get("agent_id"),
                    "agent_name": verdict.get("agent_name"),
                    "agent_color": verdict.get("agent_color"),
                    "agent_role": verdict.get("agent_role"),
                    "verdict": verdict.get("verdict"),
                    "attack": verdict.get("attack", ""),
                })

            emit_event(session_id, "adversarial_complete", {
                "translation_index": idx,
                "title": translation.get("title", ""),
                "survival_score": result["survival_score"],
                "has_fatal": result["has_fatal"],
                "verdicts": result["verdicts"],
            })

        session["adversarial_results"] = adversarial_results

        # ── Sort by survival score, emit final results ──
        ranked = sorted(
            range(len(translations)),
            key=lambda i: (
                adversarial_results[i]["survival_score"],
                -int(adversarial_results[i]["has_fatal"]),
            ),
            reverse=True,
        )

        ranked_translations = [translations[i] for i in ranked]
        ranked_adversarial = [adversarial_results[i] for i in ranked]

        session["ranked_translations"] = ranked_translations
        session["ranked_adversarial"] = ranked_adversarial

        emit_event(session_id, "results_ready", {
            "translations": ranked_translations,
            "adversarial": ranked_adversarial,
            "source_contexts": source_contexts,
            "target_context": target_context,
        })

        # Build chat context for interactive refinement
        chat_ctx = build_chat_context(
            source_contexts, target_context,
            ranked_translations, ranked_adversarial,
        )
        session["chat_context"] = chat_ctx
        session["chat_history"] = []

        emit_event(session_id, "chat_ready", {
            "message": "Interactive refinement available. Share constraints or ask questions."
        })

    except Exception as e:
        emit_event(session_id, "error", {"message": str(e)})

    finally:
        emit_event(session_id, "pipeline_complete", {})


@app.route('/api/co-researcher/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "research-translator"})


@app.route('/api/co-researcher/analyze', methods=['POST'])
def analyze():
    import requests as http_requests

    # Support either file upload OR text description
    target_bytes = None
    target_name = "research_description.txt"
    research_description = request.form.get('research_description', '').strip()

    if 'my_research' in request.files and request.files['my_research'].filename:
        target_file = request.files['my_research']
        allowed_exts = ('.pdf', '.docx', '.doc')
        if not target_file.filename.lower().endswith(allowed_exts):
            return jsonify({"error": "Your research must be a PDF or DOCX file"}), 400
        target_bytes = target_file.read()
        target_name = target_file.filename
    elif research_description:
        # Use text description as the research content
        target_bytes = research_description.encode('utf-8')
        target_name = "research_description.txt"
    else:
        return jsonify({"error": "Please describe your research or upload a file (PDF/DOCX)"}), 400

    # Support both file uploads and URLs for papers
    paper_files = request.files.getlist('papers')
    paper_urls_json = request.form.get('paper_urls', '[]')
    try:
        paper_urls = json.loads(paper_urls_json) if paper_urls_json else []
    except:
        paper_urls = []

    if (not paper_files or len(paper_files) < 1 or not paper_files[0].filename) and not paper_urls:
        return jsonify({"error": "At least one source paper is required"}), 400

    total_papers = len([p for p in paper_files if p.filename]) + len(paper_urls)
    if total_papers > 5:
        return jsonify({"error": "Maximum 5 source papers allowed"}), 400

    papers = []
    allowed_exts = ('.pdf', '.docx', '.doc')

    # Process uploaded files
    for pf in paper_files:
        if not pf.filename:
            continue
        if not pf.filename.lower().endswith(allowed_exts):
            return jsonify({"error": f"'{pf.filename}' must be PDF or DOCX"}), 400
        papers.append({"bytes": pf.read(), "name": pf.filename})

    # Download papers from URLs
    for url in paper_urls:
        try:
            resp = http_requests.get(url, timeout=30, headers={'User-Agent': 'Mozilla/5.0'})
            resp.raise_for_status()
            # Extract filename from URL or use generic name
            url_name = url.split('/')[-1].split('?')[0] or 'paper.pdf'
            if not url_name.lower().endswith(allowed_exts):
                url_name = url_name + '.pdf'
            papers.append({"bytes": resp.content, "name": url_name})
        except Exception as e:
            return jsonify({"error": f"Failed to download paper from {url}: {str(e)}"}), 400

    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "events": Queue(),
        "target_bytes": target_bytes,
        "target_name": target_name,
        "papers": papers,
        "target_text": research_description if research_description else "",
        "source_texts": [],
        "target_context": {},
        "source_contexts": [],
        "decompositions": [],
        "translations": [],
        "adversarial_results": [],
        "ranked_translations": [],
        "ranked_adversarial": [],
        "chat_context": "",
        "chat_history": [],
    }

    thread = threading.Thread(target=run_pipeline, args=(session_id,), daemon=True)
    thread.start()

    return jsonify({"session_id": session_id, "paper_count": len(papers)})


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


@app.route('/api/co-researcher/chat/<session_id>', methods=['POST'])
def chat(session_id):
    if session_id not in sessions:
        return jsonify({"error": "Session not found"}), 404

    session = sessions[session_id]
    if not session.get("chat_context"):
        return jsonify({"error": "Analysis not complete yet"}), 400

    data = request.get_json()
    user_message = data.get("message", "").strip()
    if not user_message:
        return jsonify({"error": "Message is required"}), 400

    result = handle_chat_message(
        chat_context=session["chat_context"],
        chat_history=session["chat_history"],
        user_message=user_message,
    )

    # Update chat history
    session["chat_history"].append({"role": "user", "content": user_message})
    session["chat_history"].append({"role": "assistant", "content": result["response"]})

    return jsonify(result)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5010, debug=True, threaded=True)
