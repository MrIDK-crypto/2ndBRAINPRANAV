"""
Protocol Optimizer API Routes
Endpoints for analyzing and optimizing protocols based on user context.
"""

import json
import traceback

from flask import Blueprint, Response, jsonify, request, stream_with_context, g

from services.protocol_optimizer_service import get_protocol_optimizer_service
from parsers.document_parser import DocumentParser
from database.models import SessionLocal

protocol_optimizer_bp = Blueprint('protocol_optimizer', __name__, url_prefix='/api/protocol')

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.txt', '.md'}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


@protocol_optimizer_bp.route('/optimize', methods=['POST'])
def optimize_protocol():
    """
    Analyze a protocol and suggest context-specific optimizations.

    Accepts either:
    - Form data with 'context' (text) and optional 'file' (PDF/DOCX) or 'protocol' (text)
    - JSON with 'context' and 'protocol' fields

    Returns SSE stream with analysis progress and results.
    """
    # Get context
    if request.content_type and 'multipart/form-data' in request.content_type:
        context = request.form.get('context', '').strip()
        protocol_text = request.form.get('protocol', '').strip()
    else:
        data = request.get_json() or {}
        context = data.get('context', '').strip()
        protocol_text = data.get('protocol', '').strip()

    # Handle context file upload if present (reference paper)
    context_from_file = ''
    if 'context_file' in request.files:
        context_file = request.files['context_file']
        context_filename = context_file.filename or ''

        ext = ''
        if '.' in context_filename:
            ext = '.' + context_filename.rsplit('.', 1)[1].lower()

        if ext in ALLOWED_EXTENSIONS:
            context_file_bytes = context_file.read()
            if 0 < len(context_file_bytes) <= MAX_FILE_SIZE:
                try:
                    parser = DocumentParser()
                    context_from_file = parser.parse_file_bytes(context_file_bytes, context_filename)
                    print(f"[ProtocolOptimizer] Parsed context file: {context_filename} ({len(context_from_file)} chars)", flush=True)
                except Exception as e:
                    print(f"[ProtocolOptimizer] Warning: Could not parse context file: {e}", flush=True)

    # Combine context text with file content
    if context_from_file:
        if context:
            context = f"{context}\n\n--- Reference Paper Content ---\n{context_from_file}"
        else:
            context = f"Reference Paper Content:\n{context_from_file}"

    # Validate context
    if not context:
        def error_gen():
            yield f"event: error\ndata: {json.dumps({'error': 'Please describe your experimental context (organism, tissue, what you are trying to do, any issues you are having).'})}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')

    if len(context) < 20:
        def error_gen():
            yield f"event: error\ndata: {json.dumps({'error': 'Please provide more detail about your context (at least 20 characters).'})}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')

    # Handle file upload if present
    if 'file' in request.files:
        file = request.files['file']
        filename = file.filename or ''

        # Validate extension
        ext = ''
        if '.' in filename:
            ext = '.' + filename.rsplit('.', 1)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            def error_gen():
                yield f"event: error\ndata: {json.dumps({'error': f'Unsupported file type: {ext}. Please upload PDF, DOCX, TXT, or MD file.'})}\n\n"
            return Response(error_gen(), mimetype='text/event-stream')

        # Read and parse file
        file_bytes = file.read()
        if len(file_bytes) > MAX_FILE_SIZE:
            def error_gen():
                yield f"event: error\ndata: {json.dumps({'error': 'File too large. Maximum size is 20MB.'})}\n\n"
            return Response(error_gen(), mimetype='text/event-stream')

        if len(file_bytes) == 0:
            def error_gen():
                yield f"event: error\ndata: {json.dumps({'error': 'File is empty.'})}\n\n"
            return Response(error_gen(), mimetype='text/event-stream')

        # Parse the file
        try:
            parser = DocumentParser()
            protocol_text = parser.parse_file_bytes(file_bytes, filename)
        except Exception as e:
            def error_gen():
                yield f"event: error\ndata: {json.dumps({'error': f'Could not parse file: {str(e)}'})}\n\n"
            return Response(error_gen(), mimetype='text/event-stream')

    # Validate protocol
    if not protocol_text:
        def error_gen():
            yield f"event: error\ndata: {json.dumps({'error': 'Please provide a protocol (paste text or upload a file).'})}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')

    if len(protocol_text) < 50:
        def error_gen():
            yield f"event: error\ndata: {json.dumps({'error': 'Protocol text is too short. Please provide the complete protocol.'})}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')

    # Get database session
    db = SessionLocal()

    def generate():
        try:
            service = get_protocol_optimizer_service()
            yield from service.analyze_protocol_stream(context, protocol_text, db)
        except Exception as e:
            print(f"[ProtocolOptimizer] Stream error: {e}", flush=True)
            traceback.print_exc()
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
        finally:
            db.close()

    def byte_generator():
        yield b": padding to force flush\n\n"
        for chunk in generate():
            yield chunk.encode('utf-8')
            yield b""

    response = Response(
        stream_with_context(byte_generator()),
        mimetype='text/event-stream',
        direct_passthrough=True,
        headers={
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
            'Content-Type': 'text/event-stream; charset=utf-8',
            'Transfer-Encoding': 'chunked',
        }
    )
    response.implicit_sequence_conversion = False
    return response


@protocol_optimizer_bp.route('/optimize-sync', methods=['POST'])
def optimize_protocol_sync():
    """
    Synchronous version of optimize_protocol for simpler integrations.
    Returns JSON instead of SSE stream.
    """
    data = request.get_json() or {}
    context = data.get('context', '').strip()
    protocol_text = data.get('protocol', '').strip()

    if not context or len(context) < 20:
        return jsonify({'error': 'Please provide more context about your experiment'}), 400

    if not protocol_text or len(protocol_text) < 50:
        return jsonify({'error': 'Please provide the complete protocol'}), 400

    db = SessionLocal()
    try:
        service = get_protocol_optimizer_service()

        # Collect all SSE events into final result
        final_result = {}
        for event_str in service.analyze_protocol_stream(context, protocol_text, db):
            # Parse SSE event
            if event_str.startswith("event:"):
                lines = event_str.strip().split("\n")
                event_type = lines[0].replace("event:", "").strip()
                data_line = lines[1].replace("data:", "").strip() if len(lines) > 1 else "{}"
                try:
                    event_data = json.loads(data_line)
                    if event_type == "complete":
                        final_result = event_data
                    elif event_type == "error":
                        return jsonify(event_data), 500
                except json.JSONDecodeError:
                    pass

        return jsonify(final_result)

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()


@protocol_optimizer_bp.route('/quick-check', methods=['POST'])
def quick_compatibility_check():
    """
    Quick compatibility check without full optimization.
    Just checks if protocol is compatible with user's context.
    """
    data = request.get_json() or {}
    context = data.get('context', '').strip()
    protocol_text = data.get('protocol', '').strip()

    if not context or not protocol_text:
        return jsonify({'error': 'Both context and protocol are required'}), 400

    try:
        service = get_protocol_optimizer_service()

        # Parse context and protocol
        user_context = service._parse_user_context(context)
        protocol_data = service._parse_protocol(protocol_text)

        # Check for mismatches
        mismatches = service._detect_context_mismatch(
            user_context,
            protocol_data.get("designed_for", {}),
            protocol_data.get("steps", [])
        )

        # Quick compatibility score
        compatibility_score = 100
        for m in mismatches:
            if m.get("severity") == "high":
                compatibility_score -= 30
            elif m.get("severity") == "medium":
                compatibility_score -= 15
            else:
                compatibility_score -= 5

        return jsonify({
            "compatible": compatibility_score >= 70,
            "compatibility_score": max(0, compatibility_score),
            "user_context": user_context,
            "protocol_designed_for": protocol_data.get("designed_for", {}),
            "issues": mismatches,
            "recommendation": "Protocol appears compatible" if compatibility_score >= 70 else "Protocol may need significant optimization for your context"
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@protocol_optimizer_bp.route('/search-alternatives', methods=['POST'])
def search_reagent_alternatives():
    """
    Search for alternative reagents for a specific context.
    Useful when a reagent doesn't work and user needs alternatives.
    """
    data = request.get_json() or {}
    reagent = data.get('reagent', '').strip()
    context = data.get('context', '').strip()
    purpose = data.get('purpose', '').strip()  # e.g., "nuclear staining"

    if not reagent:
        return jsonify({'error': 'Reagent name is required'}), 400

    db = SessionLocal()
    try:
        service = get_protocol_optimizer_service()

        # Parse context
        user_context = service._parse_user_context(context) if context else {}

        # Search corpus for alternatives
        corpus_results = service._search_protocol_corpus(
            {**user_context, "technique": purpose},
            {"reagents": [reagent]},
            db
        )

        # Search literature
        search_context = {
            "organism": user_context.get("organism", ""),
            "technique": f"{purpose} alternative to {reagent}"
        }
        literature = service._search_literature(search_context, {"reagents": [reagent]})

        # Generate alternatives using LLM
        try:
            response = service.openai.chat_completion(
                messages=[
                    {"role": "system", "content": """Given a reagent and context, suggest alternatives.
Return JSON:
{
    "alternatives": [
        {
            "name": "alternative reagent name",
            "why_better": "why this might work better in the given context",
            "considerations": "things to keep in mind when switching",
            "typical_concentration": "typical working concentration"
        }
    ],
    "original_issues": ["why the original reagent might not work in this context"]
}"""},
                    {"role": "user", "content": f"Reagent: {reagent}\nContext: {context or 'general'}\nPurpose: {purpose or 'not specified'}"}
                ],
                temperature=0.2,
                max_tokens=1000
            )

            text = response.choices[0].message.content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            alternatives_data = json.loads(text)

        except Exception:
            alternatives_data = {"alternatives": [], "original_issues": []}

        return jsonify({
            "reagent": reagent,
            "context": user_context,
            "alternatives": alternatives_data.get("alternatives", []),
            "original_issues": alternatives_data.get("original_issues", []),
            "literature_support": literature.get("pubmed", [])[:3],
            "corpus_evidence": corpus_results.get("typical_parameters", {})
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    finally:
        db.close()
