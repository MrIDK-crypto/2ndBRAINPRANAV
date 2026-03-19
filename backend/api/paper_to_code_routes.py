"""
Paper-to-Code API Routes
Generates Python implementations from research paper text via SSE streaming.
"""

import json
import traceback

from flask import Blueprint, Response, request, stream_with_context

from services.auth_service import require_auth
from services.paper_to_code_service import get_paper_to_code_service

paper_to_code_bp = Blueprint('paper_to_code', __name__, url_prefix='/api/paper-to-code')


@paper_to_code_bp.route('/generate', methods=['POST'])
@require_auth
def generate_code():
    """Generate a Python implementation from research paper text. Returns SSE stream."""
    data = request.get_json() or {}
    paper_text = (data.get('paper_text') or '').strip()
    field = (data.get('field') or '').strip()
    paper_type = (data.get('paper_type') or 'experimental').strip()
    focus_section = (data.get('focus_section') or '').strip()

    if len(paper_text) < 200:
        def error_gen():
            yield f"event: error\ndata: {json.dumps({'error': f'Paper text must be at least 200 characters (currently {len(paper_text)}).'})}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')

    def generate():
        try:
            service = get_paper_to_code_service()
            yield from service.generate(paper_text, field=field, paper_type=paper_type, focus_section=focus_section)
        except Exception as e:
            print(f"[PaperToCode] Stream error: {e}", flush=True)
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
