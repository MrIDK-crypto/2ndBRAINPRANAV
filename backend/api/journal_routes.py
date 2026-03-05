"""
High-Impact Journal Predictor — Public API endpoint.
No authentication required.
"""

import json
import traceback

from flask import Blueprint, Response, request, stream_with_context

from services.journal_scorer_service import get_journal_scorer_service

journal_bp = Blueprint('journal', __name__, url_prefix='/api/journal')

ALLOWED_EXTENSIONS = {'.pdf', '.docx'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


@journal_bp.route('/analyze', methods=['POST'])
def analyze_manuscript():
    """Analyze a manuscript and return SSE stream of results. No auth required."""

    if 'file' not in request.files:
        def error_gen():
            yield f"event: error\ndata: {json.dumps({'error': 'No file provided. Please upload a PDF or DOCX file.'})}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')

    file = request.files['file']
    filename = file.filename or ''

    # Validate extension
    ext = ''
    if '.' in filename:
        ext = '.' + filename.rsplit('.', 1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        err_ext = ext or 'unknown'
        def error_gen():
            yield f"event: error\ndata: {json.dumps({'error': 'Unsupported file type: ' + err_ext + '. Please upload a PDF or DOCX file.'})}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')

    # Read file bytes
    file_bytes = file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        def error_gen():
            yield f"event: error\ndata: {json.dumps({'error': 'File too large. Maximum size is 50MB.'})}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')

    if len(file_bytes) == 0:
        def error_gen():
            yield f"event: error\ndata: {json.dumps({'error': 'File is empty.'})}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')

    def generate():
        try:
            service = get_journal_scorer_service()
            yield from service.analyze_manuscript(file_bytes, filename)
        except Exception as e:
            print(f"[Journal] Stream error: {e}", flush=True)
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
