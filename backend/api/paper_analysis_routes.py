"""
Paper Analysis API Routes
==========================
Endpoints for uploading and analyzing research papers.

POST /api/papers/analyze         - Upload PDF/DOCX, get structured analysis (JSON)
POST /api/papers/analyze/stream  - Upload PDF/DOCX, get SSE stream of analysis progress
"""

import json
import traceback

from flask import Blueprint, Response, jsonify, request, stream_with_context

from services.paper_analysis_service import get_paper_analysis_service

paper_analysis_bp = Blueprint('paper_analysis', __name__, url_prefix='/api/papers')

ALLOWED_EXTENSIONS = {'.pdf', '.docx'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


def _validate_upload():
    """Validate file upload. Returns (file_bytes, filename, ext) or (None, None, error_msg)."""
    if 'file' not in request.files:
        return None, None, 'No file provided. Please upload a PDF or DOCX file.'

    file = request.files['file']
    filename = file.filename or ''

    ext = ''
    if '.' in filename:
        ext = '.' + filename.rsplit('.', 1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return None, None, f'Unsupported file type: {ext or "unknown"}. Please upload a PDF or DOCX file.'

    file_bytes = file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        return None, None, 'File too large. Maximum size is 50MB.'
    if len(file_bytes) == 0:
        return None, None, 'File is empty.'

    return file_bytes, filename, None


@paper_analysis_bp.route('/analyze', methods=['POST'])
def analyze_paper():
    """
    Upload a PDF or DOCX file and get a structured analysis.

    Returns JSON with:
    - paper_type: detected type (experimental, review, meta_analysis, case_report, protocol)
    - type_detection: confidence and signals
    - sections: type-specific analysis
    - related_literature: related papers from OpenAlex
    - related_protocols: matching protocols from corpus
    - gaps: detected knowledge gaps
    - suggestions: experiment suggestions (experimental papers only)
    """
    file_bytes, filename, error = _validate_upload()
    if error:
        return jsonify({'error': error}), 400

    # Optional tenant_id from auth (not required for this endpoint)
    tenant_id = None
    try:
        from flask import g
        tenant_id = getattr(g, 'tenant_id', None)
    except Exception:
        pass

    try:
        service = get_paper_analysis_service()
        result = service.analyze(file_bytes, filename, tenant_id=tenant_id)
        return jsonify(result)
    except Exception as e:
        print(f"[PaperAnalysis] Error: {e}", flush=True)
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@paper_analysis_bp.route('/analyze/stream', methods=['POST'])
def analyze_paper_stream():
    """
    Upload a PDF or DOCX file and stream analysis progress via SSE.

    SSE events:
    - event: progress  data: {step, message}
    - event: result    data: {section, data}
    - event: complete  data: {summary}
    - event: error     data: {error}
    """
    file_bytes, filename, error = _validate_upload()
    if error:
        def error_gen():
            yield f"event: error\ndata: {json.dumps({'error': error})}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')

    # Optional tenant_id
    tenant_id = None
    try:
        from flask import g
        tenant_id = getattr(g, 'tenant_id', None)
    except Exception:
        pass

    def generate():
        try:
            service = get_paper_analysis_service()
            yield from service.analyze_stream(file_bytes, filename, tenant_id=tenant_id)
        except Exception as e:
            print(f"[PaperAnalysis] Stream error: {e}", flush=True)
            traceback.print_exc()
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

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
