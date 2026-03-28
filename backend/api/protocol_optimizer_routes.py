"""
Protocol Optimizer API Routes
Endpoints for analyzing and optimizing protocols based on user context.
Includes both public (no auth) and context-aware (auth required) versions.
"""

import json
import os
import traceback

from flask import Blueprint, Response, jsonify, request, stream_with_context, g

from services.protocol_optimizer_service import get_protocol_optimizer_service
from services.auth_service import require_auth
from parsers.document_parser import DocumentParser
from database.models import SessionLocal

protocol_optimizer_bp = Blueprint('protocol_optimizer', __name__, url_prefix='/api/protocol')

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.txt', '.md'}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


def _sse(event: str, data: dict) -> str:
    """Format SSE event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@protocol_optimizer_bp.route('/optimize', methods=['POST'])
def optimize_protocol():
    """
    Analyze a protocol and suggest context-specific optimizations.

    Accepts either:
    - Form data with 'context' (text) and optional 'file' (PDF/DOCX) or 'protocol' (text)
    - JSON with 'context' and 'protocol' fields

    Returns SSE stream with analysis progress and results.
    """
    # Get context text
    if request.content_type and 'multipart/form-data' in request.content_type:
        context_text = request.form.get('context', '').strip()
        protocol_text = request.form.get('protocol', '').strip()
    else:
        data = request.get_json() or {}
        context_text = data.get('context', '').strip()
        protocol_text = data.get('protocol', '').strip()

    # Read file bytes immediately (fast) - we'll parse inside the generator
    context_file_bytes = None
    context_filename = ''
    if 'context_file' in request.files:
        context_file = request.files['context_file']
        context_filename = context_file.filename or ''
        ext = ''
        if '.' in context_filename:
            ext = '.' + context_filename.rsplit('.', 1)[1].lower()
        if ext in ALLOWED_EXTENSIONS:
            context_file_bytes = context_file.read()
            if len(context_file_bytes) > MAX_FILE_SIZE:
                context_file_bytes = None

    protocol_file_bytes = None
    protocol_filename = ''
    if 'file' in request.files:
        file = request.files['file']
        protocol_filename = file.filename or ''
        ext = ''
        if '.' in protocol_filename:
            ext = '.' + protocol_filename.rsplit('.', 1)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            def error_gen():
                yield _sse("error", {"error": f"Unsupported file type: {ext}. Please upload PDF, DOCX, TXT, or MD file."})
            return Response(error_gen(), mimetype='text/event-stream')
        protocol_file_bytes = file.read()
        if len(protocol_file_bytes) > MAX_FILE_SIZE:
            def error_gen():
                yield _sse("error", {"error": "File too large. Maximum size is 20MB."})
            return Response(error_gen(), mimetype='text/event-stream')
        if len(protocol_file_bytes) == 0:
            def error_gen():
                yield _sse("error", {"error": "File is empty."})
            return Response(error_gen(), mimetype='text/event-stream')

    # Basic validation - need at least some input
    if not context_text and not context_file_bytes:
        def error_gen():
            yield _sse("error", {"error": "Please describe your experimental context or upload a reference paper."})
        return Response(error_gen(), mimetype='text/event-stream')

    if not protocol_text and not protocol_file_bytes:
        def error_gen():
            yield _sse("error", {"error": "Please provide a protocol (paste text or upload a file)."})
        return Response(error_gen(), mimetype='text/event-stream')

    # Get database session
    db = SessionLocal()

    def generate():
        nonlocal context_text, protocol_text
        try:
            # ── Parse context file if present ──
            if context_file_bytes:
                yield _sse("progress", {"step": 0, "message": f"Parsing reference paper: {context_filename}...", "percent": 2})
                try:
                    parser = DocumentParser()
                    context_from_file = parser.parse_file_bytes(context_file_bytes, context_filename)
                    print(f"[ProtocolOptimizer] Parsed context file: {context_filename} ({len(context_from_file)} chars)", flush=True)
                    if context_text:
                        context_text = f"{context_text}\n\n--- Reference Paper Content ---\n{context_from_file}"
                    else:
                        context_text = f"Reference Paper Content:\n{context_from_file}"
                except Exception as e:
                    print(f"[ProtocolOptimizer] Warning: Could not parse context file: {e}", flush=True)
                    yield _sse("progress", {"step": 0, "message": f"Warning: Could not parse reference paper, continuing...", "percent": 3})

            # ── Validate context ──
            if not context_text or len(context_text) < 20:
                yield _sse("error", {"error": "Please provide more detail about your context (at least 20 characters)."})
                return

            # ── Parse protocol file if present ──
            if protocol_file_bytes:
                yield _sse("progress", {"step": 0, "message": f"Parsing protocol: {protocol_filename}...", "percent": 4})
                try:
                    parser = DocumentParser()
                    protocol_text = parser.parse_file_bytes(protocol_file_bytes, protocol_filename)
                    print(f"[ProtocolOptimizer] Parsed protocol file: {protocol_filename} ({len(protocol_text)} chars)", flush=True)
                except Exception as e:
                    yield _sse("error", {"error": f"Could not parse protocol file: {str(e)}"})
                    return

            # ── Validate protocol ──
            if not protocol_text or len(protocol_text) < 50:
                yield _sse("error", {"error": "Protocol text is too short. Please provide the complete protocol."})
                return

            # ── Run the optimization ──
            service = get_protocol_optimizer_service()
            yield from service.analyze_protocol_stream(context_text, protocol_text, db)

        except Exception as e:
            print(f"[ProtocolOptimizer] Stream error: {e}", flush=True)
            traceback.print_exc()
            yield _sse("error", {"error": str(e)})
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
        }
    )
    # Let Flask-CORS handle CORS headers instead of manual headers
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


# ── Context-Aware Endpoints (Auth Required) ─────────────────────────────────

def _generate_protocol_context_analysis(
    profile: dict,
    protocols: list,
    failed_experiments: list,
    protocol_text: str,
    context_text: str
) -> dict:
    """Generate context-aware analysis for protocol optimization.

    Returns structure matching frontend expectations:
    - equipment_match: {score, assessment, matched_equipment}
    - past_protocol_insights: {summary, relevant_protocols}
    - risk_warnings: [string array]
    - optimization_strategy: {approach, rationale}
    - competitive_advantage: string
    - sources: {field: [{title, source_type, excerpt}]}
    """
    try:
        from services.openai_client import get_openai_client
        openai = get_openai_client()

        # Build summary of past protocols
        past_protocols_summary = ""
        protocol_titles = []
        if protocols:
            for p in protocols[:5]:
                title = p.get('metadata', {}).get('title', 'Protocol')
                protocol_titles.append(title)
                past_protocols_summary += f"- {title}: {p.get('content', '')[:200]}\n"

        # Build summary of failed experiments
        failed_summary = ""
        if failed_experiments:
            failed_summary = "\n".join([
                f"- {f.get('metadata', {}).get('title', 'Issue')}: {f.get('content', '')[:200]}"
                for f in failed_experiments[:3]
            ])

        equipment_list = profile.get('equipment', [])
        methods_list = profile.get('methodologies', [])

        prompt = f"""Analyze this protocol optimization request against the lab's history.

LAB PROFILE:
- Equipment: {', '.join(equipment_list) or 'Not specified'}
- Methods: {', '.join(methods_list) or 'Not specified'}
- Research Focus: {', '.join(profile.get('research_focus_areas', [])) or 'Not specified'}

PAST PROTOCOLS:
{past_protocols_summary or 'None found'}

KNOWN ISSUES/FAILURES:
{failed_summary or 'None found'}

CURRENT PROTOCOL TO OPTIMIZE (excerpt):
{protocol_text[:1500]}

USER CONTEXT:
{context_text[:500]}

Provide specific, actionable analysis. Return JSON with EXACTLY this structure:
{{
    "equipment_match": {{
        "score": <0-100 integer indicating how well protocol matches lab equipment>,
        "assessment": "<1-2 sentence summary of equipment compatibility>",
        "matched_equipment": ["<equipment from lab that can be used>"]
    }},
    "past_protocol_insights": {{
        "summary": "<2-3 sentence summary of how past protocols can help>",
        "relevant_protocols": ["<specific protocol names that are relevant>"]
    }},
    "risk_warnings": ["<specific warning 1>", "<specific warning 2>"],
    "optimization_strategy": {{
        "approach": "<recommended strategy in 1 sentence>",
        "rationale": "<why this approach based on their lab capabilities>"
    }},
    "competitive_advantage": "<what unique advantage this lab has for this protocol>"
}}"""

        response = openai.chat_completion(
            messages=[
                {"role": "system", "content": "You are a lab protocol expert helping researchers optimize protocols based on their specific lab setup and history. Be specific and reference their actual past work."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1500,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)

        # Ensure structure matches frontend expectations
        if 'equipment_match' in result:
            em = result['equipment_match']
            if 'score' not in em:
                em['score'] = 70  # Default
            if 'assessment' not in em:
                em['assessment'] = em.get('recommendation', 'Equipment compatibility analysis available.')
            if 'matched_equipment' not in em:
                em['matched_equipment'] = em.get('compatible', equipment_list[:5])

        if 'past_protocol_insights' in result:
            ppi = result['past_protocol_insights']
            if 'summary' not in ppi:
                ppi['summary'] = ppi.get('recommendation', 'Insights from past protocols available.')
            if 'relevant_protocols' not in ppi:
                ppi['relevant_protocols'] = ppi.get('relevant_protocols', protocol_titles[:3])

        # Convert risk_warnings to array if needed
        if 'risk_warnings' in result and isinstance(result['risk_warnings'], dict):
            rw = result['risk_warnings']
            warnings_list = []
            if 'based_on_failures' in rw:
                warnings_list.extend(rw['based_on_failures'])
            if 'general_risks' in rw:
                warnings_list.extend(rw['general_risks'])
            result['risk_warnings'] = warnings_list[:5]

        # Ensure optimization_strategy has correct structure
        if 'optimization_strategy' in result:
            os = result['optimization_strategy']
            if 'rationale' not in os:
                os['rationale'] = os.get('expected_improvement', 'Based on your lab capabilities.')

        result["has_context"] = True
        result["profile_summary"] = {
            "equipment": equipment_list,
            "methodologies": methods_list,
            "protocols_found": len(protocols),
            "failures_found": len(failed_experiments)
        }

        # Include sources from lab profile
        if profile.get('sources'):
            result['sources'] = profile['sources']

        return result

    except Exception as e:
        print(f"[ProtocolOptimizer] Context analysis generation failed: {e}")
        return {
            "has_context": True,
            "error": str(e),
            "profile_summary": profile,
            "sources": profile.get('sources', {})
        }


def _fetch_protocol_context(query: str, tenant_id: str, db=None, top_k: int = 15) -> dict:
    """
    Fetch relevant protocols and lab notes from the knowledge base.
    Returns context dict with documents categorized by type AND a structured lab profile.

    IMPORTANT: Uses DIVERSE document sources from the database (Drive, Box, Email, Slack, etc.)
    rather than just search results which may be biased toward one source type.
    """
    try:
        from services.lab_profile_service import get_lab_profile_service
        profile_service = get_lab_profile_service()

        # PRIORITY: Fetch diverse documents directly from database across ALL source types
        all_documents = []
        lab_profile = None

        if db:
            diverse_docs = profile_service.fetch_diverse_documents(tenant_id, db, max_per_source=10, total_max=50)
            if diverse_docs:
                all_documents = diverse_docs
                lab_profile = profile_service.build_profile(tenant_id, diverse_docs)
                print(f"[ProtocolOptimizer] Built profile from {len(diverse_docs)} diverse DB documents", flush=True)

        # Fallback: Use Pinecone search if no DB docs
        if not all_documents and os.getenv("PINECONE_API_KEY"):
            from services.enhanced_search_service import get_enhanced_search_service
            from vector_stores.pinecone_store import get_hybrid_store

            vector_store = get_hybrid_store()
            enhanced_service = get_enhanced_search_service()

            seen_ids = set()
            search_queries = [
                query,  # Original query
                "protocol procedure method technique",
                "failed experiment troubleshooting problem error",
                "equipment reagent buffer solution",
            ]

            for search_query in search_queries:
                result = enhanced_service.enhanced_search(
                    query=search_query,
                    tenant_id=tenant_id,
                    vector_store=vector_store,
                    top_k=top_k,
                    use_reranking=True,
                    use_mmr=True,
                )
                for doc in result.get("results", []):
                    doc_id = doc.get("id") or doc.get("metadata", {}).get("doc_id")
                    if doc_id and doc_id not in seen_ids:
                        seen_ids.add(doc_id)
                        all_documents.append(doc)

            if all_documents and not lab_profile:
                lab_profile = profile_service.build_profile(tenant_id, all_documents)
                print(f"[ProtocolOptimizer] Built profile from {len(all_documents)} search results (fallback)", flush=True)

        if not all_documents:
            return {"documents": [], "protocols": [], "failed_experiments": [], "summary": "", "profile": None, "count": 0}

        # Categorize documents
        protocols = []
        failed_experiments = []
        other_docs = []

        for doc in all_documents:
            content_lower = doc.get("content", "").lower()
            title_lower = doc.get("metadata", {}).get("title", "").lower()
            combined = content_lower + " " + title_lower

            # Detect protocols
            if any(kw in combined for kw in ["protocol", "procedure", "method", "reagent", "incubat", "centrifug", "buffer"]):
                protocols.append(doc)
            # Detect failed experiments
            elif any(kw in combined for kw in ["failed", "didn't work", "troubleshoot", "problem", "error", "not working"]):
                failed_experiments.append(doc)
            else:
                other_docs.append(doc)

        # Build STRUCTURED context summary with instructions
        context_instructions = """
=== CONTEXT-AWARE PROTOCOL OPTIMIZATION INSTRUCTIONS ===
You have access to this researcher's lab profile. Use it to:

1. **LEVERAGE PAST PROTOCOLS**:
   - Reference specific parameters that worked in their lab
   - Suggest using their proven equipment and reagents
   - Copy successful approaches from similar protocols

2. **AVOID KNOWN ISSUES**:
   - Check failed experiments for pitfalls to avoid
   - Flag if the protocol uses something that caused problems before
   - Suggest alternatives based on what worked

3. **MATCH LAB CAPABILITIES**:
   - Optimize for their specific equipment
   - Use reagents/buffers they already have
   - Consider their expertise level

4. **PROVIDE EXPLICIT REASONING**:
   - Say "Based on your past protocol X, use Y setting"
   - Say "Your lab had issues with Z, so instead try W"
   - Reference specific documents when making suggestions

"""

        context_parts = [context_instructions]

        # Add structured profile info
        profile_dict = lab_profile.to_dict()
        context_parts.append("=== LAB PROFILE ===")
        if profile_dict.get("equipment"):
            context_parts.append(f"**Lab Equipment:** {', '.join(profile_dict['equipment'])}")
        if profile_dict.get("methodologies"):
            context_parts.append(f"**Common Methods:** {', '.join(profile_dict['methodologies'])}")
        if profile_dict.get("research_focus_areas"):
            context_parts.append(f"**Research Focus:** {', '.join(profile_dict['research_focus_areas'])}")

        if protocols:
            context_parts.append("\n=== PAST PROTOCOLS FROM YOUR LAB ===")
            for p in protocols[:4]:
                title = p.get("metadata", {}).get("title", "Untitled")
                content = p.get("content", "")[:800]
                context_parts.append(f"**Protocol: {title}**\n{content}\n")

        if failed_experiments:
            context_parts.append("\n=== KNOWN ISSUES / FAILED EXPERIMENTS ===")
            context_parts.append("**CRITICAL: Review these before optimizing - avoid repeating mistakes!**\n")
            for f in failed_experiments[:4]:
                title = f.get("metadata", {}).get("title", "Note")
                content = f.get("content", "")[:500]
                context_parts.append(f"**Issue: {title}**\n{content}\n")

        if other_docs and len(protocols) < 3:
            context_parts.append("\n=== RELATED LAB DOCUMENTS ===")
            for d in other_docs[:3]:
                title = d.get("metadata", {}).get("title", "Document")
                content = d.get("content", "")[:400]
                context_parts.append(f"**{title}:**\n{content}\n")

        return {
            "documents": all_documents,
            "protocols": protocols,
            "failed_experiments": failed_experiments,
            "summary": "\n".join(context_parts),
            "profile": profile_dict,
            "count": len(all_documents)
        }

    except Exception as e:
        print(f"[ProtocolOptimizer] Context fetch error: {e}", flush=True)
        traceback.print_exc()
        return {"documents": [], "protocols": [], "failed_experiments": [], "summary": "", "profile": None, "error": str(e)}


@protocol_optimizer_bp.route('/research-context', methods=['GET'])
@require_auth
def get_research_context():
    """
    Fetch pre-computed research context for auto-population.
    Returns lab info, common techniques, organisms, etc.
    """
    tenant_id = g.tenant_id

    try:
        from database.models import Tenant, SessionLocal

        db = SessionLocal()
        try:
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()

            # Check for cached research summary (shared with journal)
            if tenant and tenant.research_summary:
                summary = tenant.research_summary
                return jsonify({
                    "success": True,
                    "has_context": True,
                    "research_description": summary.get("suggested_description", ""),
                    "research_areas": summary.get("research_areas", []),
                    "methodologies": summary.get("methodologies", []),
                    "cached": True
                }), 200

            # No cached summary
            return jsonify({
                "success": True,
                "has_context": False,
                "research_description": "",
                "message": "No research context cached. Generate it from High Impact Journal first.",
                "cached": False
            }), 200

        finally:
            db.close()

    except Exception as e:
        print(f"[ProtocolOptimizer] Research context error: {e}", flush=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@protocol_optimizer_bp.route('/optimize-with-context', methods=['POST'])
@require_auth
def optimize_protocol_with_context():
    """
    Analyze a protocol with lab-specific context from the knowledge base.
    Requires authentication. Uses past protocols, failed experiments, and
    lab notes to provide personalized optimization suggestions.

    Accepts same input as /optimize:
    - Form data with 'context' (text) and optional 'file' (PDF/DOCX) or 'protocol' (text)
    - JSON with 'context' and 'protocol' fields

    SSE stream includes additional 'lab_context' event with documents used.
    """
    tenant_id = g.tenant_id

    # Get context text
    if request.content_type and 'multipart/form-data' in request.content_type:
        context_text = request.form.get('context', '').strip()
        protocol_text = request.form.get('protocol', '').strip()
    else:
        data = request.get_json() or {}
        context_text = data.get('context', '').strip()
        protocol_text = data.get('protocol', '').strip()

    # Read file bytes immediately
    context_file_bytes = None
    context_filename = ''
    if 'context_file' in request.files:
        context_file = request.files['context_file']
        context_filename = context_file.filename or ''
        ext = ''
        if '.' in context_filename:
            ext = '.' + context_filename.rsplit('.', 1)[1].lower()
        if ext in ALLOWED_EXTENSIONS:
            context_file_bytes = context_file.read()
            if len(context_file_bytes) > MAX_FILE_SIZE:
                context_file_bytes = None

    protocol_file_bytes = None
    protocol_filename = ''
    if 'file' in request.files:
        file = request.files['file']
        protocol_filename = file.filename or ''
        ext = ''
        if '.' in protocol_filename:
            ext = '.' + protocol_filename.rsplit('.', 1)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            def error_gen():
                yield _sse("error", {"error": f"Unsupported file type: {ext}. Please upload PDF, DOCX, TXT, or MD file."})
            return Response(error_gen(), mimetype='text/event-stream')
        protocol_file_bytes = file.read()
        if len(protocol_file_bytes) > MAX_FILE_SIZE:
            def error_gen():
                yield _sse("error", {"error": "File too large. Maximum size is 20MB."})
            return Response(error_gen(), mimetype='text/event-stream')
        if len(protocol_file_bytes) == 0:
            def error_gen():
                yield _sse("error", {"error": "File is empty."})
            return Response(error_gen(), mimetype='text/event-stream')

    # Basic validation
    if not context_text and not context_file_bytes:
        def error_gen():
            yield _sse("error", {"error": "Please describe your experimental context or upload a reference paper."})
        return Response(error_gen(), mimetype='text/event-stream')

    if not protocol_text and not protocol_file_bytes:
        def error_gen():
            yield _sse("error", {"error": "Please provide a protocol (paste text or upload a file)."})
        return Response(error_gen(), mimetype='text/event-stream')

    db = SessionLocal()

    def generate():
        nonlocal context_text, protocol_text
        try:
            # ── Parse context file if present ──
            if context_file_bytes:
                yield _sse("progress", {"step": 0, "message": f"Parsing reference paper: {context_filename}...", "percent": 2})
                try:
                    parser = DocumentParser()
                    context_from_file = parser.parse_file_bytes(context_file_bytes, context_filename)
                    print(f"[ProtocolOptimizer] Parsed context file: {context_filename} ({len(context_from_file)} chars)", flush=True)
                    if context_text:
                        context_text = f"{context_text}\n\n--- Reference Paper Content ---\n{context_from_file}"
                    else:
                        context_text = f"Reference Paper Content:\n{context_from_file}"
                except Exception as e:
                    print(f"[ProtocolOptimizer] Warning: Could not parse context file: {e}", flush=True)
                    yield _sse("progress", {"step": 0, "message": "Warning: Could not parse reference paper, continuing...", "percent": 3})

            # ── Validate context ──
            if not context_text or len(context_text) < 20:
                yield _sse("error", {"error": "Please provide more detail about your context (at least 20 characters)."})
                return

            # ── Parse protocol file if present ──
            if protocol_file_bytes:
                yield _sse("progress", {"step": 0, "message": f"Parsing protocol: {protocol_filename}...", "percent": 4})
                try:
                    parser = DocumentParser()
                    protocol_text = parser.parse_file_bytes(protocol_file_bytes, protocol_filename)
                    print(f"[ProtocolOptimizer] Parsed protocol file: {protocol_filename} ({len(protocol_text)} chars)", flush=True)
                except Exception as e:
                    yield _sse("error", {"error": f"Could not parse protocol file: {str(e)}"})
                    return

            # ── Validate protocol ──
            if not protocol_text or len(protocol_text) < 50:
                yield _sse("error", {"error": "Protocol text is too short. Please provide the complete protocol."})
                return

            # ── Fetch lab context ──
            yield _sse("progress", {"step": 0, "message": "Searching lab knowledge base for relevant protocols and notes...", "percent": 6})

            # Search using both context and protocol for best matches
            search_query = f"{context_text[:500]} {protocol_text[:500]}"
            lab_context = _fetch_protocol_context(search_query, tenant_id, db=db, top_k=10)

            # Get profile from context
            profile = lab_context.get("profile")

            # Emit lab_context event so frontend knows what was found
            yield _sse("lab_context", {
                "documents_used": lab_context.get("count", 0),
                "protocols_found": len(lab_context.get("protocols", [])),
                "failed_experiments_found": len(lab_context.get("failed_experiments", [])),
                "has_context": bool(lab_context.get("summary")),
                "has_profile": profile is not None
            })

            # ── Generate context analysis (ALWAYS emit, even without profile) ──
            doc_count = lab_context.get("count", 0)
            protocols_count = len(lab_context.get("protocols", []))
            failures_count = len(lab_context.get("failed_experiments", []))

            print(f"[ProtocolOptimizer] Lab context search results: {doc_count} docs, {protocols_count} protocols, {failures_count} failures, profile={profile is not None}", flush=True)

            if profile and lab_context.get("summary"):
                try:
                    yield _sse("progress", {"step": 0, "message": "Analyzing protocol against your lab's history...", "percent": 8})

                    context_analysis = _generate_protocol_context_analysis(
                        profile=profile,
                        protocols=lab_context.get("protocols", []),
                        failed_experiments=lab_context.get("failed_experiments", []),
                        protocol_text=protocol_text[:2000],
                        context_text=context_text[:1000]
                    )
                    yield _sse("context_analysis", context_analysis)
                    print(f"[ProtocolOptimizer] Context analysis complete with {len(context_analysis.get('equipment_match', {}).get('matched_equipment', []))} matched equipment", flush=True)
                except Exception as e:
                    print(f"[ProtocolOptimizer] Context analysis generation failed: {e}", flush=True)
                    traceback.print_exc()
                    yield _sse("context_analysis", {"has_context": False, "error": str(e)})
            else:
                # ALWAYS emit context_analysis event - even when no profile, explain why
                no_context_reason = []
                if not os.getenv("PINECONE_API_KEY"):
                    no_context_reason.append("Vector database not configured")
                elif doc_count == 0:
                    no_context_reason.append("No documents found in your knowledge base - try syncing more data sources")
                elif not profile:
                    no_context_reason.append("Lab profile could not be generated from available documents")

                fallback_analysis = {
                    "has_context": False,
                    "no_context_reason": "; ".join(no_context_reason) if no_context_reason else "No relevant context found",
                    "documents_searched": doc_count,
                    "tip": "Sync more documents (Slack, Google Drive, etc.) to enable personalized protocol optimization"
                }
                yield _sse("context_analysis", fallback_analysis)
                print(f"[ProtocolOptimizer] No lab context: {fallback_analysis['no_context_reason']}", flush=True)

            # ── Enhance context with lab documents ──
            if lab_context.get("summary"):
                enhanced_context = f"""
{lab_context['summary']}

=== USER'S CURRENT CONTEXT ===
{context_text}

=== END LAB CONTEXT ===
"""
                print(f"[ProtocolOptimizer] Added {lab_context.get('count', 0)} lab documents as context (profile confidence: {profile.get('confidence_score', 0):.0%})" if profile else f"[ProtocolOptimizer] Added {lab_context.get('count', 0)} lab documents as context", flush=True)
            else:
                enhanced_context = context_text
                print("[ProtocolOptimizer] No lab context available, proceeding with user context only", flush=True)

            # ── Run the optimization with enhanced context ──
            service = get_protocol_optimizer_service()
            yield from service.analyze_protocol_stream(enhanced_context, protocol_text, db)

        except Exception as e:
            print(f"[ProtocolOptimizer] Context stream error: {e}", flush=True)
            traceback.print_exc()
            yield _sse("error", {"error": str(e)})
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
        }
    )
    response.implicit_sequence_conversion = False
    return response
