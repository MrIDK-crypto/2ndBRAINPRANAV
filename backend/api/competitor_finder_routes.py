"""
Competitor Finder API Routes
Searches OpenAlex, arXiv, and NIH Reporter for competing labs and preprints.
Returns SSE stream with results.
"""

import json
import traceback

from flask import Blueprint, Response, request, stream_with_context

from services.auth_service import require_auth
from services.competitor_finder_service import get_competitor_finder_service

competitor_finder_bp = Blueprint('competitor_finder', __name__, url_prefix='/api/competitor-finder')


@competitor_finder_bp.route('/search', methods=['POST'])
@require_auth
def search_competitors():
    """Find competing labs, preprints, and grants for a research paper. Returns SSE stream."""
    data = request.get_json() or {}
    paper_text = (data.get('paper_text') or '').strip()
    field = (data.get('field') or '').strip()
    keywords = data.get('keywords') or []

    if len(paper_text) < 100:
        def error_gen():
            yield f"event: error\ndata: {json.dumps({'error': f'Paper text must be at least 100 characters (currently {len(paper_text)}).'})}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')

    def generate():
        try:
            service = get_competitor_finder_service()
            yield from service.find_competitors(paper_text, field=field, keywords=keywords)
        except Exception as e:
            print(f"[CompetitorFinder] Stream error: {e}", flush=True)
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
