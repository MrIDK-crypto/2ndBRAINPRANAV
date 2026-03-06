"""
Research Translator — Blueprint for app_v2.py
Endpoints under /api/co-researcher:
  POST /analyze    — Upload "my research" + "papers I read", starts pipeline
  GET  /stream/<id> — SSE event stream
  POST /chat/<id>   — Interactive refinement chat
"""

import uuid
import json
import threading
from queue import Queue, Empty

from flask import Blueprint, request, jsonify, Response

from co_researcher.parser import parse_document
from co_researcher.decomposer import extract_context, decompose_layers
from co_researcher.translator import translate_insight
from co_researcher.adversarial import run_adversarial
from co_researcher.chat import build_chat_context, handle_chat_message

research_translator_bp = Blueprint(
    'research_translator', __name__, url_prefix='/api/co-researcher'
)

# In-memory session store for translation pipelines
_rt_sessions = {}


def _emit_event(session_id: str, event_type: str, data: dict):
    if session_id in _rt_sessions:
        _rt_sessions[session_id]["events"].put({
            "event": event_type,
            "data": data,
        })


def _run_pipeline(session_id: str):
    session = _rt_sessions[session_id]

    try:
        papers = session["papers"]
        total_papers = len(papers)

        # Phase 1: Parse
        _emit_event(session_id, "parsing_status", {
            "stage": "target", "progress": 5,
            "message": "Parsing your research document..."
        })
        target_text = parse_document(session["target_bytes"], session["target_name"])
        session["target_text"] = target_text

        _emit_event(session_id, "parsing_status", {
            "stage": "target", "progress": 20,
            "message": "Your research parsed. Parsing source papers..."
        })

        source_texts = []
        for i, paper in enumerate(papers):
            pct = 20 + int((i + 1) / total_papers * 30)
            _emit_event(session_id, "parsing_status", {
                "stage": "source", "progress": pct,
                "paper_index": i,
                "message": f"Parsing paper {i+1}/{total_papers}: {paper['name']}..."
            })
            text = parse_document(paper["bytes"], paper["name"])
            source_texts.append(text)

        session["source_texts"] = source_texts
        _emit_event(session_id, "parsing_status", {
            "stage": "complete", "progress": 50,
            "message": "All documents parsed."
        })

        # Phase 2: Context extraction + decomposition
        _emit_event(session_id, "context_extracting", {
            "message": "Extracting structured context from your research..."
        })
        target_context = extract_context(target_text, "target")
        session["target_context"] = target_context

        _emit_event(session_id, "context_extracted", {
            "role": "target",
            "context": target_context,
        })

        source_contexts = []
        all_decompositions = []

        for i, (paper, text) in enumerate(zip(papers, source_texts)):
            _emit_event(session_id, "context_extracting", {
                "paper_index": i,
                "paper_name": paper["name"],
                "message": f"Extracting context from paper {i+1}: {paper['name']}..."
            })
            source_ctx = extract_context(text, "source")
            source_contexts.append(source_ctx)

            _emit_event(session_id, "context_extracted", {
                "role": "source",
                "paper_index": i,
                "paper_name": paper["name"],
                "context": source_ctx,
            })

            items_to_decompose = (
                source_ctx.get("key_methods", [])[:3] +
                source_ctx.get("key_findings", [])[:2]
            )

            _emit_event(session_id, "decomposition_started", {
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

                _emit_event(session_id, "layer_extracted", {
                    "paper_index": i,
                    "paper_name": paper["name"],
                    "item_index": j,
                    "item_name": item.get("name", item.get("finding", "Unknown")),
                    "layers": layers,
                })

        session["source_contexts"] = source_contexts
        session["decompositions"] = all_decompositions

        _emit_event(session_id, "decomposition_complete", {
            "total_decompositions": len(all_decompositions),
        })

        # Phase 3: Translation
        _emit_event(session_id, "translation_started", {
            "total": len(all_decompositions),
            "message": "Translating insights into your research domain..."
        })

        translations = []
        for idx, decomp in enumerate(all_decompositions):
            paper_idx = decomp["paper_index"]
            source_ctx = source_contexts[paper_idx]

            _emit_event(session_id, "translating_insight", {
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

            _emit_event(session_id, "translation_complete", {
                "index": idx,
                "translation": translation,
            })

        session["translations"] = translations

        # Phase 4: Adversarial stress-test
        _emit_event(session_id, "adversarial_started", {
            "total_translations": len(translations),
            "message": "Stress-testing each translation..."
        })

        adversarial_results = []

        for idx, translation in enumerate(translations):
            paper_idx = translation["paper_index"]
            source_ctx = source_contexts[paper_idx]

            _emit_event(session_id, "adversarial_testing", {
                "translation_index": idx,
                "title": translation.get("title", ""),
                "message": f"Stress-testing translation {idx+1}/{len(translations)}..."
            })

            result = run_adversarial(translation, source_ctx, target_context)
            result["translation_index"] = idx
            adversarial_results.append(result)

            for verdict in result.get("verdicts", []):
                _emit_event(session_id, "agent_verdict", {
                    "translation_index": idx,
                    "translation_title": translation.get("title", ""),
                    "agent_id": verdict.get("agent_id"),
                    "agent_name": verdict.get("agent_name"),
                    "agent_color": verdict.get("agent_color"),
                    "agent_role": verdict.get("agent_role"),
                    "verdict": verdict.get("verdict"),
                    "attack": verdict.get("attack", ""),
                })

            _emit_event(session_id, "adversarial_complete", {
                "translation_index": idx,
                "title": translation.get("title", ""),
                "survival_score": result["survival_score"],
                "has_fatal": result["has_fatal"],
                "verdicts": result["verdicts"],
            })

        session["adversarial_results"] = adversarial_results

        # Sort by survival score
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

        _emit_event(session_id, "results_ready", {
            "translations": ranked_translations,
            "adversarial": ranked_adversarial,
            "source_contexts": source_contexts,
            "target_context": target_context,
        })

        chat_ctx = build_chat_context(
            source_contexts, target_context,
            ranked_translations, ranked_adversarial,
        )
        session["chat_context"] = chat_ctx
        session["chat_history"] = []

        _emit_event(session_id, "chat_ready", {
            "message": "Interactive refinement available. Share constraints or ask questions."
        })

    except Exception as e:
        _emit_event(session_id, "error", {"message": str(e)})

    finally:
        _emit_event(session_id, "pipeline_complete", {})


@research_translator_bp.route('/analyze', methods=['POST'])
def rt_analyze():
    if 'my_research' not in request.files:
        return jsonify({"error": "'my_research' file is required (PDF or DOCX)"}), 400

    paper_files = request.files.getlist('papers')
    if not paper_files or len(paper_files) < 1:
        return jsonify({"error": "At least one source paper is required"}), 400
    if len(paper_files) > 5:
        return jsonify({"error": "Maximum 5 source papers allowed"}), 400

    target_file = request.files['my_research']
    allowed_exts = ('.pdf', '.docx', '.doc')

    if not target_file.filename.lower().endswith(allowed_exts):
        return jsonify({"error": "Your research must be a PDF or DOCX file"}), 400

    papers = []
    for pf in paper_files:
        if not pf.filename.lower().endswith(allowed_exts):
            return jsonify({"error": f"'{pf.filename}' must be PDF or DOCX"}), 400
        papers.append({"bytes": pf.read(), "name": pf.filename})

    session_id = str(uuid.uuid4())
    _rt_sessions[session_id] = {
        "events": Queue(),
        "target_bytes": target_file.read(),
        "target_name": target_file.filename,
        "papers": papers,
        "target_text": "",
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

    thread = threading.Thread(target=_run_pipeline, args=(session_id,), daemon=True)
    thread.start()

    return jsonify({"session_id": session_id, "paper_count": len(papers)})


@research_translator_bp.route('/stream/<session_id>', methods=['GET'])
def rt_stream(session_id):
    if session_id not in _rt_sessions:
        return jsonify({"error": "Session not found"}), 404

    def event_stream():
        while True:
            try:
                event = _rt_sessions[session_id]["events"].get(timeout=120)
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


@research_translator_bp.route('/chat/<session_id>', methods=['POST'])
def rt_chat(session_id):
    if session_id not in _rt_sessions:
        return jsonify({"error": "Session not found"}), 404

    session = _rt_sessions[session_id]
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

    session["chat_history"].append({"role": "user", "content": user_message})
    session["chat_history"].append({"role": "assistant", "content": result["response"]})

    return jsonify(result)
