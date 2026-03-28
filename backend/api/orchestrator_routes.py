"""API route for the Chat Orchestrator — POST /api/chat/orchestrated"""

import json
import logging
from flask import Blueprint, request, g, Response, stream_with_context
from services.auth_service import require_auth

logger = logging.getLogger(__name__)

orchestrator_bp = Blueprint("orchestrator", __name__, url_prefix="/api/chat")


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@orchestrator_bp.route("/orchestrated", methods=["POST"])
@require_auth
def orchestrated_chat():
    tenant_id = g.tenant_id
    user_id = g.user_id

    # Parse request (multipart or JSON)
    if request.content_type and "multipart" in request.content_type:
        message = request.form.get("message", "")
        metadata_str = request.form.get("metadata", "{}")
        try:
            metadata = json.loads(metadata_str)
        except json.JSONDecodeError:
            metadata = {}
        uploaded_files = request.files.getlist("files")
    else:
        data = request.get_json() or {}
        message = data.get("message", "")
        metadata = data
        uploaded_files = []

    power_hint = metadata.get("power_hint")
    conversation_id = metadata.get("conversation_id")

    file_bytes = None
    filename = None
    if uploaded_files:
        f = uploaded_files[0]
        file_bytes = f.read()
        filename = f.filename

    def generate():
        try:
            # --- LAYER 1: Intent Gate ---
            yield _sse_event("thinking", {"step": "Analyzing your request..."})

            from services.chat_orchestrator.intent_gate import IntentGate
            gate = IntentGate()
            classification = gate.classify(message, power_hint=power_hint)

            if not classification["needs_powers"]:
                yield _sse_event("fallback", {"reason": "standard_chat"})
                yield _sse_event("done", {})
                return

            powers = classification["powers"]
            skip_router = classification["skip_router"]

            # --- CONTEXT INJECTION ---
            yield _sse_event("thinking", {"step": "Loading your research context..."})

            from services.chat_orchestrator.context_injector import inject_context
            context_package = inject_context(tenant_id, message)

            yield _sse_event("context_loaded", {
                "profile_fields": context_package.get("profile_fields", []),
                "chunks_found": context_package.get("chunks_found", 0),
            })

            # --- LAYER 2: Tool Router ---
            if skip_router and len(powers) == 1:
                from services.chat_orchestrator.tool_router import extract_params_simple
                args = extract_params_simple(message, powers[0], context_package)
                tool_calls = [{"service": powers[0], "args": args}]
            else:
                yield _sse_event("thinking", {"step": "Determining which tools to use..."})
                from services.chat_orchestrator.tool_router import route
                tool_calls = route(message, context_package)

            if not tool_calls:
                yield _sse_event("fallback", {"reason": "no_tools_selected"})
                yield _sse_event("done", {})
                return

            # Check if HIJ needs a file but none provided
            for tc in tool_calls:
                if tc["service"] == "hij" and not file_bytes:
                    raw_text = tc.get("args", {}).get("paper_text") or message
                    if len(raw_text) < 200:
                        yield _sse_event("file_needed", {
                            "service": "hij",
                            "message": "Please attach your manuscript to score it.",
                        })
                        yield _sse_event("done", {})
                        return

            # --- LAYER 3: Parallel Execution ---
            service_names = [tc["service"] for tc in tool_calls]
            yield _sse_event("services_started", {"services": service_names})

            from services.chat_orchestrator.parallel_executor import execute
            results = execute(
                tool_calls=tool_calls,
                context_package=context_package,
                file_bytes=file_bytes,
                filename=filename,
                tenant_id=tenant_id,
            )

            for result in results:
                yield _sse_event("service_complete", {
                    "service": result["service"],
                    "status": result["status"],
                })

            # --- RESPONSE MERGER ---
            yield _sse_event("thinking", {"step": "Generating your personalized summary..."})

            from services.chat_orchestrator.response_merger import merge
            merged = merge(
                results=results,
                research_profile=context_package.get("research_profile"),
                user_message=message,
            )

            # --- PERSIST TO CONVERSATION ---
            _save_to_conversation(
                tenant_id=tenant_id,
                user_id=user_id,
                conversation_id=conversation_id,
                user_message=message,
                merged_result=merged,
            )

            # --- SEND FINAL RESULT ---
            yield _sse_event("result", merged)
            yield _sse_event("done", {})

        except Exception as e:
            logger.error(f"Orchestrator error: {e}", exc_info=True)
            yield _sse_event("error", {"message": str(e)})
            yield _sse_event("done", {})

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _save_to_conversation(
    tenant_id: str,
    user_id: str,
    conversation_id: str | None,
    user_message: str,
    merged_result: dict,
):
    try:
        from database.models import SessionLocal, ChatConversation, ChatMessage
        from database.models import generate_uuid
        from datetime import datetime, timezone

        db = SessionLocal()
        try:
            if conversation_id:
                conv = db.query(ChatConversation).filter(
                    ChatConversation.id == conversation_id,
                    ChatConversation.tenant_id == tenant_id,
                ).first()
            else:
                conv = None

            if not conv:
                conv = ChatConversation(
                    id=generate_uuid(),
                    tenant_id=tenant_id,
                    user_id=user_id,
                    title=user_message[:100],
                )
                db.add(conv)
                db.flush()

            now = datetime.now(timezone.utc)

            user_msg = ChatMessage(
                id=generate_uuid(),
                conversation_id=conv.id,
                tenant_id=tenant_id,
                role="user",
                content=user_message,
                message_type="text",
                created_at=now,
            )
            db.add(user_msg)

            tab_labels = [t["label"] for t in merged_result.get("tabs", [])]
            content_text = f"Power analysis: {', '.join(tab_labels)}"

            assistant_msg = ChatMessage(
                id=generate_uuid(),
                conversation_id=conv.id,
                tenant_id=tenant_id,
                role="assistant",
                content=content_text,
                message_type="power_result",
                extra_data=merged_result,
                created_at=now,
            )
            db.add(assistant_msg)

            conv.last_message_at = now
            db.commit()

        finally:
            db.close()

    except Exception as e:
        logger.error(f"Failed to save orchestrated conversation: {e}", exc_info=True)
