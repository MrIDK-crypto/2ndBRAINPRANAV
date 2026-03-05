"""
Co-Researcher API Routes
REST + SSE endpoints for research sessions, messaging, and hypothesis testing.
"""

import json
from flask import Blueprint, request, jsonify, g, Response, stream_with_context

from database.models import (
    SessionLocal, ResearchSession, ResearchMessage, Hypothesis, Evidence
)
from services.auth_service import require_auth
from services.co_researcher_service import get_co_researcher_service


co_researcher_bp = Blueprint('co_researcher', __name__, url_prefix='/api/co-researcher')


def get_db():
    return SessionLocal()


# ============================================================================
# SESSIONS
# ============================================================================

@co_researcher_bp.route('/sessions', methods=['GET'])
@require_auth
def list_sessions():
    """List research sessions for the current user."""
    db = get_db()
    try:
        service = get_co_researcher_service()
        limit = request.args.get('limit', 20, type=int)
        offset = request.args.get('offset', 0, type=int)
        sessions = service.list_sessions(g.tenant_id, g.user_id, db, limit=limit, offset=offset)
        return jsonify({"success": True, "sessions": sessions})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        db.close()


@co_researcher_bp.route('/sessions', methods=['POST'])
@require_auth
def create_session():
    """Create a new research session with an initial message."""
    db = get_db()
    try:
        data = request.get_json() or {}
        initial_message = data.get('initial_message', '').strip()
        if not initial_message:
            return jsonify({"success": False, "error": "initial_message is required"}), 400

        service = get_co_researcher_service()
        session_data = service.create_session(g.tenant_id, g.user_id, initial_message, db)
        return jsonify({"success": True, "session": session_data}), 201
    except Exception as e:
        db.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        db.close()


@co_researcher_bp.route('/sessions/<session_id>', methods=['GET'])
@require_auth
def get_session(session_id: str):
    """Get a research session with messages and hypotheses."""
    db = get_db()
    try:
        service = get_co_researcher_service()
        session_data = service.get_session(session_id, g.tenant_id, db)
        if not session_data:
            return jsonify({"success": False, "error": "Session not found"}), 404
        return jsonify({"success": True, "session": session_data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        db.close()


@co_researcher_bp.route('/sessions/<session_id>', methods=['PUT'])
@require_auth
def update_session(session_id: str):
    """Update a session (title, status, tags)."""
    db = get_db()
    try:
        data = request.get_json() or {}
        service = get_co_researcher_service()
        session_data = service.update_session(session_id, g.tenant_id, data, db)
        if not session_data:
            return jsonify({"success": False, "error": "Session not found"}), 404
        return jsonify({"success": True, "session": session_data})
    except Exception as e:
        db.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        db.close()


@co_researcher_bp.route('/sessions/<session_id>', methods=['DELETE'])
@require_auth
def delete_session(session_id: str):
    """Archive (soft delete) a session."""
    db = get_db()
    try:
        service = get_co_researcher_service()
        if not service.delete_session(session_id, g.tenant_id, db):
            return jsonify({"success": False, "error": "Session not found"}), 404
        return jsonify({"success": True})
    except Exception as e:
        db.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        db.close()


# ============================================================================
# STREAMING MESSAGE
# ============================================================================

@co_researcher_bp.route('/sessions/<session_id>/messages/stream', methods=['POST'])
@require_auth
def send_message_stream(session_id: str):
    """
    Send a message and receive a streamed AI response via SSE.

    SSE events:
    - action: {type, text} — progress indicators
    - chunk: {content} — answer text chunks
    - plan_update: {plan} — updated research plan
    - brief_update: {brief} — updated research brief
    - context_update: {documents, pubmed_papers, gaps} — context data
    - hypothesis_update: {hypothesis} — new/updated hypothesis
    - done: {message_id, sources, actions} — streaming complete
    - error: {error} — error occurred
    """
    data = request.get_json() or {}
    message = data.get('message', '').strip()
    skip_user_save = data.get('skip_user_save', False)
    if not message:
        def error_gen():
            yield f"event: error\ndata: {json.dumps({'error': 'Message is required'})}\n\n"
        return Response(error_gen(), mimetype='text/event-stream')

    tenant_id = g.tenant_id

    def generate():
        db = SessionLocal()
        try:
            service = get_co_researcher_service()
            yield from service.process_message_stream(session_id, tenant_id, message, db, skip_user_save=skip_user_save)
        except Exception as e:
            import traceback
            print(f"[CoResearcher] Stream error: {e}", flush=True)
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


# ============================================================================
# HYPOTHESES
# ============================================================================

@co_researcher_bp.route('/sessions/<session_id>/hypotheses', methods=['GET'])
@require_auth
def list_hypotheses(session_id: str):
    """List hypotheses for a session with their evidence."""
    db = get_db()
    try:
        hypotheses = db.query(Hypothesis).filter(
            Hypothesis.session_id == session_id,
            Hypothesis.tenant_id == g.tenant_id,
        ).order_by(Hypothesis.created_at).all()
        return jsonify({
            "success": True,
            "hypotheses": [h.to_dict(include_evidence=True) for h in hypotheses]
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        db.close()


@co_researcher_bp.route('/sessions/<session_id>/hypotheses/<hypothesis_id>/test', methods=['POST'])
@require_auth
def retest_hypothesis(session_id: str, hypothesis_id: str):
    """Re-test an existing hypothesis (re-gather evidence)."""
    db = get_db()
    try:
        hypothesis = db.query(Hypothesis).filter(
            Hypothesis.id == hypothesis_id,
            Hypothesis.session_id == session_id,
            Hypothesis.tenant_id == g.tenant_id,
        ).first()

        if not hypothesis:
            return jsonify({"success": False, "error": "Hypothesis not found"}), 404

        # Delete old evidence and re-test
        db.query(Evidence).filter(Evidence.hypothesis_id == hypothesis_id).delete()
        hypothesis.status = "testing"
        db.commit()

        # Trigger re-test via message processing
        service = get_co_researcher_service()
        # This is a non-streaming re-test — for streaming, use the message endpoint
        return jsonify({
            "success": True,
            "message": "Hypothesis re-test queued. Send a follow-up message to trigger re-evaluation."
        })
    except Exception as e:
        db.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        db.close()


# ============================================================================
# SYNTHESIS
# ============================================================================

@co_researcher_bp.route('/sessions/<session_id>/synthesize', methods=['POST'])
@require_auth
def synthesize_session(session_id: str):
    """Generate a comprehensive synthesis via SSE streaming."""
    tenant_id = g.tenant_id

    def generate():
        db = SessionLocal()
        try:
            service = get_co_researcher_service()
            session = db.query(ResearchSession).filter(
                ResearchSession.id == session_id,
                ResearchSession.tenant_id == tenant_id,
            ).first()
            if not session:
                yield f"event: error\ndata: {json.dumps({'error': 'Session not found'})}\n\n"
                return

            history = service._get_conversation_history(session_id, db)
            yield from service._handle_synthesize_stream(session, history, [], db)
        except Exception as e:
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
            'X-Accel-Buffering': 'no',
            'Content-Type': 'text/event-stream; charset=utf-8',
        }
    )
    response.implicit_sequence_conversion = False
    return response
