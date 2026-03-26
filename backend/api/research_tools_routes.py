"""
Research Tools API Routes
- Citation Analyzer: "Who Should I Cite?"
- Competitor Finder: "Find My Competitors"
- Protocol Remix: Cross-organism protocol matching
"""

import json
import traceback

from flask import Blueprint, Response, jsonify, request, stream_with_context

from services.citation_analyzer_service import get_citation_analyzer_service
from services.competitor_finder_service import get_competitor_finder_service
from parsers.document_parser import DocumentParser

research_tools_bp = Blueprint('research_tools', __name__, url_prefix='/api/research-tools')

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.txt', '.md'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


def _extract_manuscript_text(request) -> tuple:
    """Extract manuscript text from file upload or text input."""

    # Check for text input first
    if request.content_type and 'application/json' in request.content_type:
        data = request.get_json() or {}
        text = data.get('text', '').strip()
        if text:
            return text, None

    # Check form data
    text = request.form.get('text', '').strip()
    if text and len(text) > 200:
        return text, None

    # Check for file upload
    if 'file' not in request.files:
        return None, "No manuscript provided. Please upload a PDF/DOCX or paste your text."

    file = request.files['file']
    filename = file.filename or ''

    # Validate extension
    ext = ''
    if '.' in filename:
        ext = '.' + filename.rsplit('.', 1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return None, f"Unsupported file type: {ext}. Please upload PDF, DOCX, TXT, or MD file."

    # Read file bytes
    file_bytes = file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        return None, "File too large. Maximum size is 50MB."
    if len(file_bytes) == 0:
        return None, "File is empty."

    # Parse the file
    try:
        parser = DocumentParser()
        text = parser.parse_file_bytes(file_bytes, filename)
        return text, None
    except Exception as e:
        return None, f"Could not parse file: {str(e)}"


# ============================================================================
# CITATION ANALYZER - "Who Should I Cite?"
# ============================================================================

@research_tools_bp.route('/citations/analyze', methods=['POST'])
def analyze_citations():
    """
    Analyze manuscript citations and find gaps.

    Accepts:
    - Form data with 'file' (PDF/DOCX) or 'text'
    - JSON with 'text' field

    Returns SSE stream with analysis progress and results.
    """

    text, error = _extract_manuscript_text(request)

    if error:
        def error_gen():
            yield f"event: error\ndata: {json.dumps({'error': error})}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')

    if len(text) < 500:
        def error_gen():
            yield f"event: error\ndata: {json.dumps({'error': 'Manuscript text is too short. Please provide at least 500 characters.'})}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')

    def generate():
        try:
            service = get_citation_analyzer_service()
            yield from service.analyze_stream(text)
        except Exception as e:
            print(f"[CitationAnalyzer] Stream error: {e}", flush=True)
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


# ============================================================================
# COMPETITOR FINDER - "Find My Competitors"
# ============================================================================

@research_tools_bp.route('/competitors/analyze', methods=['POST'])
def analyze_competitors():
    """
    Find competing labs, preprints, and grants.

    Accepts:
    - Form data with 'file' (PDF/DOCX) or 'text'
    - JSON with 'text' field

    Returns SSE stream with competitor analysis.
    """

    text, error = _extract_manuscript_text(request)

    if error:
        def error_gen():
            yield f"event: error\ndata: {json.dumps({'error': error})}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')

    if len(text) < 500:
        def error_gen():
            yield f"event: error\ndata: {json.dumps({'error': 'Manuscript text is too short. Please provide at least 500 characters.'})}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')

    def generate():
        try:
            service = get_competitor_finder_service()
            yield from service.analyze_stream(text)
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


# ============================================================================
# PROTOCOL REMIX - Cross-organism protocol matching
# ============================================================================

@research_tools_bp.route('/protocol-remix', methods=['POST'])
def protocol_remix():
    """
    Find protocols that can be adapted across organisms/techniques.

    Request JSON:
    {
        "source_organism": "mouse",
        "target_organism": "zebrafish",
        "technique": "cardiac tissue imaging",
        "context": "optional additional context"
    }

    Returns JSON with matching protocols and adaptation suggestions.
    """

    data = request.get_json() or {}
    source_organism = data.get('source_organism', '').strip()
    target_organism = data.get('target_organism', '').strip()
    technique = data.get('technique', '').strip()
    context = data.get('context', '').strip()

    if not target_organism or not technique:
        return jsonify({'error': 'target_organism and technique are required'}), 400

    try:
        from services.protocol_reference_store import get_store
        from services.openai_client import get_openai_client

        store = get_store()
        openai = get_openai_client()

        # Search for protocols with source organism + technique
        search_query = f"{source_organism} {technique}" if source_organism else technique
        similar_protocols = store.find_similar_protocols(search_query, top_k=15)

        if not similar_protocols:
            return jsonify({
                'success': True,
                'source_organism': source_organism,
                'target_organism': target_organism,
                'technique': technique,
                'protocols_found': 0,
                'matches': [],
                'message': 'No matching protocols found in corpus'
            })

        # Use LLM to generate adaptation suggestions
        adaptation_suggestions = []

        for protocol in similar_protocols[:5]:
            try:
                response = openai.chat_completion(
                    messages=[{
                        "role": "system",
                        "content": f"""You are a lab protocol expert. Given a protocol designed for {source_organism or 'general use'},
suggest specific adaptations needed for {target_organism}.

Consider:
- Anatomical differences
- Reagent compatibility
- Timing/dosage adjustments
- Equipment modifications
- Common pitfalls when adapting between these organisms

Be specific and practical."""
                    }, {
                        "role": "user",
                        "content": f"""Protocol: {protocol.get('title', 'Unknown')}
Technique: {technique}
Steps: {', '.join(protocol.get('step_verbs', [])[:10])}
Reagents: {', '.join(protocol.get('reagents', [])[:10])}

How should this be adapted for {target_organism}?"""
                    }],
                    temperature=0.3,
                    max_tokens=500
                )

                adaptation = response.choices[0].message.content.strip()

                adaptation_suggestions.append({
                    'protocol_title': protocol.get('title', ''),
                    'source': protocol.get('source', ''),
                    'similarity': protocol.get('similarity', 0),
                    'original_steps': protocol.get('step_verbs', [])[:10],
                    'original_reagents': protocol.get('reagents', [])[:10],
                    'adaptation_for_target': adaptation,
                    'confidence': 'high' if protocol.get('similarity', 0) > 0.3 else 'medium'
                })

            except Exception as e:
                print(f"[ProtocolRemix] Adaptation generation failed: {e}")
                continue

        return jsonify({
            'success': True,
            'source_organism': source_organism or 'general',
            'target_organism': target_organism,
            'technique': technique,
            'protocols_found': len(similar_protocols),
            'adaptations': adaptation_suggestions,
            'all_matches': [{
                'title': p.get('title', ''),
                'source': p.get('source', ''),
                'similarity': p.get('similarity', 0),
                'num_steps': p.get('num_steps', 0)
            } for p in similar_protocols]
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
