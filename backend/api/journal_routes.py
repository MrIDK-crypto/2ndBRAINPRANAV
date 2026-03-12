"""
High-Impact Journal Predictor — Public API endpoints.
No authentication required.
"""

import json
import threading
import traceback

from flask import Blueprint, Response, jsonify, request, stream_with_context

from services.journal_scorer_service import get_journal_scorer_service

journal_bp = Blueprint('journal', __name__, url_prefix='/api/journal')

ALLOWED_EXTENSIONS = {'.pdf', '.docx'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


@journal_bp.route('/analyze', methods=['POST'])
def analyze_manuscript():
    """Analyze a manuscript (file upload) or research description (text) and return SSE stream of results. No auth required."""

    # Check if this is a text-based submission
    research_text = request.form.get('text', '').strip()

    # Optional: user-provided publication year (overrides auto-detection)
    user_publication_year = None
    pub_year_str = request.form.get('publication_year', '').strip()
    if pub_year_str:
        try:
            user_publication_year = int(pub_year_str)
        except ValueError:
            pass

    if research_text:
        # Text-based research description
        word_count = len(research_text.split())
        if word_count < 100:
            def error_gen():
                yield f"event: error\ndata: {json.dumps({'error': f'Please provide at least 100 words describing your research (currently {word_count}).'})}\n\n"
            return Response(error_gen(), mimetype='text/event-stream')

        def generate():
            try:
                service = get_journal_scorer_service()
                yield from service.analyze_manuscript(None, 'research_description.txt', manuscript_url=None, raw_text=research_text, user_publication_year=user_publication_year)
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

    # File-based submission
    if 'file' not in request.files:
        def error_gen():
            yield f"event: error\ndata: {json.dumps({'error': 'No file or research description provided. Please upload a PDF/DOCX or describe your research.'})}\n\n"
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

    # Upload manuscript to S3 for viewing later
    manuscript_url = None
    try:
        import uuid
        from services.s3_service import S3Service
        s3 = S3Service()
        s3_key = f"journal-manuscripts/{uuid.uuid4()}{ext}"
        content_type = 'application/pdf' if ext == '.pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        uploaded_key, err = s3.upload_bytes(file_bytes, s3_key, content_type=content_type)
        if uploaded_key:
            manuscript_url = s3.get_presigned_url(uploaded_key, expiration=86400)  # 24h
    except Exception as e:
        print(f"[Journal] S3 upload skipped: {e}")

    def generate():
        try:
            service = get_journal_scorer_service()
            yield from service.analyze_manuscript(file_bytes, filename, manuscript_url=manuscript_url, user_publication_year=user_publication_year)
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


# ── Data Management Endpoints ────────────────────────────────────────────────

@journal_bp.route('/populate', methods=['POST'])
def populate_journals():
    """Populate journal database from OpenAlex. Runs in background thread."""
    field = request.args.get('field')
    force = request.args.get('force', 'false').lower() == 'true'

    from services.journal_data_service import get_journal_data_service
    svc = get_journal_data_service()

    if svc.check_freshness() and not field and not force:
        return jsonify({"status": "skipped", "message": "Journal data is fresh (<30 days old). Use ?force=true to override."})

    def run_populate():
        try:
            svc.populate_journals(field=field)
            print(f"[Journal] Population complete for {'all fields' if not field else field}")
        except Exception as e:
            print(f"[Journal] Population error: {e}")
            traceback.print_exc()

    thread = threading.Thread(target=run_populate, daemon=True)
    thread.start()

    return jsonify({"status": "started", "message": f"Populating {'all fields' if not field else field} in background"})


@journal_bp.route('/enrich-sjr', methods=['POST'])
def enrich_sjr():
    """Enrich existing journal data with SJR scores via Firecrawl scraping. Runs in background."""
    field = request.args.get('field')

    from services.journal_data_service import get_journal_data_service
    svc = get_journal_data_service()

    def run_enrich():
        try:
            svc.enrich_with_sjr(field=field)
            svc._recompute_tiers_with_sjr(field=field)
            print(f"[Journal] SJR enrichment complete for {'all fields' if not field else field}")
        except Exception as e:
            print(f"[Journal] SJR enrichment error: {e}")
            traceback.print_exc()

    thread = threading.Thread(target=run_enrich, daemon=True)
    thread.start()

    return jsonify({"status": "started", "message": f"Enriching SJR data for {'all fields' if not field else field}"})


@journal_bp.route('/full-refresh', methods=['POST'])
def full_refresh():
    """Full pipeline: OpenAlex + SJR + recompute tiers. Runs in background.
    Call this monthly to keep data fresh."""
    field = request.args.get('field')
    force = request.args.get('force', 'false').lower() == 'true'

    from services.journal_data_service import get_journal_data_service
    svc = get_journal_data_service()

    if svc.check_freshness() and not force:
        return jsonify({"status": "skipped", "message": "Journal data is fresh (<30 days old). Use ?force=true to override."})

    def run_refresh():
        try:
            svc.full_refresh(field=field)
        except Exception as e:
            print(f"[Journal] Full refresh error: {e}")
            traceback.print_exc()

    thread = threading.Thread(target=run_refresh, daemon=True)
    thread.start()

    return jsonify({"status": "started", "message": f"Full refresh for {'all fields' if not field else field}"})


@journal_bp.route('/data-summary', methods=['GET'])
def data_summary():
    """Get summary of all stored journal data — counts per field and tier."""
    from services.journal_data_service import get_journal_data_service
    svc = get_journal_data_service()
    return jsonify(svc.get_data_summary())
