"""
High-Impact Journal Predictor — API endpoints.
Includes both public (no auth) and context-aware (auth required) versions.
"""

import json
import os
import threading
import traceback

from flask import Blueprint, Response, jsonify, request, stream_with_context, g

from services.journal_scorer_service import get_journal_scorer_service
from services.auth_service import require_auth

journal_bp = Blueprint('journal', __name__, url_prefix='/api/journal')

ALLOWED_EXTENSIONS = {'.pdf', '.docx'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# CORS headers for SSE responses
SSE_CORS_HEADERS = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, Authorization',
}


def _sse_error_response(error_msg: str) -> Response:
    """Create an SSE error response with CORS headers."""
    def error_gen():
        yield f"event: error\ndata: {json.dumps({'error': error_msg})}\n\n"
    return Response(error_gen(), mimetype='text/event-stream', headers=SSE_CORS_HEADERS)


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
        if word_count < 50:
            return _sse_error_response(f'Please provide at least 50 words describing your research (currently {word_count}).')

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
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization',
            }
        )
        response.implicit_sequence_conversion = False
        return response

    # File-based submission
    if 'file' not in request.files:
        return _sse_error_response('No file or research description provided. Please upload a PDF/DOCX or describe your research.')

    file = request.files['file']
    filename = file.filename or ''

    # Validate extension
    ext = ''
    if '.' in filename:
        ext = '.' + filename.rsplit('.', 1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        err_ext = ext or 'unknown'
        return _sse_error_response(f'Unsupported file type: {err_ext}. Please upload a PDF or DOCX file.')

    # Read file bytes
    file_bytes = file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        return _sse_error_response('File too large. Maximum size is 50MB.')

    if len(file_bytes) == 0:
        return _sse_error_response('File is empty.')

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
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
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


# ── Context-Aware Endpoints (Auth Required) ─────────────────────────────────

def _fetch_lab_context(query: str, tenant_id: str, db=None, top_k: int = 15) -> dict:
    """
    Fetch relevant documents and build a STRUCTURED lab profile.
    Returns both raw documents and a structured profile for context-aware analysis.

    IMPORTANT: Uses DIVERSE document sources from the database (Drive, Box, Email, Slack, etc.)
    rather than just search results which may be biased toward one source type.
    """
    try:
        from services.lab_profile_service import get_lab_profile_service
        profile_service = get_lab_profile_service()

        # PRIORITY: Build profile from diverse DB sources (not just search results)
        lab_profile = None
        all_documents = []

        if db:
            # Fetch diverse documents directly from database across ALL source types
            diverse_docs = profile_service.fetch_diverse_documents(tenant_id, db, max_per_source=10, total_max=50)

            if diverse_docs:
                all_documents = diverse_docs
                lab_profile = profile_service.build_profile(tenant_id, diverse_docs)
                print(f"[Journal] Built profile from {len(diverse_docs)} diverse DB documents (sources: {set(d.get('metadata', {}).get('source_type', 'unknown') for d in diverse_docs[:10])})", flush=True)

        # Fallback: Use Pinecone search if no DB docs or no DB session
        if not lab_profile or lab_profile.confidence_score == 0:
            if os.getenv("PINECONE_API_KEY"):
                from services.enhanced_search_service import get_enhanced_search_service
                from vector_stores.pinecone_store import get_hybrid_store

                vector_store = get_hybrid_store()
                enhanced_service = get_enhanced_search_service()

                seen_ids = set()
                search_queries = [
                    query,  # Original query
                    "research methodology experiments findings",
                    "publication journal paper published",
                    "protocol procedure technique method"
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
                    print(f"[Journal] Built profile from {len(all_documents)} search results (fallback)", flush=True)

        if not lab_profile:
            return {"documents": [], "summary": "", "profile": None, "count": 0}

        # Create the formatted context for prompts
        profile_context = lab_profile.to_prompt_context()

        return {
            "documents": all_documents,
            "summary": profile_context,
            "profile": lab_profile.to_dict(),
            "count": len(all_documents)
        }

    except Exception as e:
        print(f"[Journal] Context fetch error: {e}", flush=True)
        traceback.print_exc()
        return {"documents": [], "summary": "", "profile": None, "error": str(e)}


def _generate_journal_context_analysis(profile: dict, manuscript_excerpt: str) -> dict:
    """
    Generate context-aware analysis showing how lab profile informs journal selection.

    Returns structure matching frontend expectations:
    - equipment_match: {score, assessment, matched_equipment}
    - methodology_match: {score, assessment, relevant_methods}
    - publication_fit: {tier_match, typical_tier, suggested_tier_range}
    - competitive_advantages: [string array]
    - potential_concerns: [string array]
    - sources: {field: [{title, source_type, excerpt}]}
    """
    try:
        from services.openai_client import get_openai_client
        openai = get_openai_client()

        equipment = profile.get('equipment', [])
        methodologies = profile.get('methodologies', [])
        preferred_journals = profile.get('preferred_journals', [])
        typical_tier = profile.get('typical_impact_tier', 3)

        prompt = f"""Analyze this manuscript against the researcher's lab profile for journal selection context.

LAB PROFILE:
- Equipment: {', '.join(equipment[:10]) or 'Not specified'}
- Methodologies: {', '.join(methodologies[:10]) or 'Not specified'}
- Typical Publication Tier: {typical_tier} (1=Nature/Science, 4=Specialized)
- Preferred Journals: {', '.join(preferred_journals[:5]) or 'Not specified'}
- Research Focus: {', '.join(profile.get('research_focus_areas', [])[:5]) or 'Not specified'}

MANUSCRIPT EXCERPT:
{manuscript_excerpt[:2000]}

Return JSON with EXACTLY this structure:
{{
    "equipment_match": {{
        "score": <0-100 indicating how well manuscript methods match lab equipment>,
        "assessment": "<1 sentence about equipment fit>",
        "matched_equipment": ["<equipment from lab that's relevant>"]
    }},
    "methodology_match": {{
        "score": <0-100 indicating methodology alignment>,
        "assessment": "<1 sentence about methodology fit>",
        "relevant_methods": ["<methods from lab that apply>"]
    }},
    "publication_fit": {{
        "tier_match": "<matches_history|stretch_goal|below_potential|new_direction>",
        "typical_tier": {typical_tier},
        "suggested_tier_range": "<e.g., 'Tier 2-3' based on manuscript quality vs lab history>"
    }},
    "competitive_advantages": ["<specific advantage 1 based on lab profile>", "<advantage 2>"],
    "potential_concerns": ["<concern 1 if any>"]
}}"""

        response = openai.chat_completion(
            messages=[
                {"role": "system", "content": "You are a publication advisor analyzing how a researcher's track record informs journal selection strategy."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=1000,
            response_format={"type": "json_object"}
        )

        result = json.loads(response.choices[0].message.content)
        result["has_context"] = True

        # Include sources from lab profile
        if profile.get('sources'):
            result['sources'] = profile['sources']

        return result

    except Exception as e:
        print(f"[Journal] Context analysis generation failed: {e}")
        return {
            "has_context": True,
            "error": str(e),
            "sources": profile.get('sources', {}) if profile else {}
        }


def compute_research_summary(tenant_id: str, db=None) -> dict:
    """
    Compute and store research summary for a tenant.
    Called after document sync completes.
    """
    try:
        if not os.getenv("PINECONE_API_KEY"):
            return {"success": False, "error": "Knowledge base not configured"}

        from services.enhanced_search_service import get_enhanced_search_service
        from vector_stores.pinecone_store import get_hybrid_store
        from openai import AzureOpenAI
        from database.models import Tenant, SessionLocal, utc_now

        vector_store = get_hybrid_store()
        enhanced_service = get_enhanced_search_service()

        # Search for research-related documents with broad query
        research_queries = [
            "research methodology experiments findings results",
            "hypothesis study analysis data conclusions",
            "protocol procedure technique method"
        ]

        all_documents = []
        seen_ids = set()

        for query in research_queries:
            result = enhanced_service.enhanced_search(
                query=query,
                tenant_id=tenant_id,
                vector_store=vector_store,
                top_k=10,
                use_reranking=True,
                use_mmr=True,
            )
            for doc in result.get("results", []):
                doc_id = doc.get("id") or doc.get("metadata", {}).get("doc_id")
                if doc_id and doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    all_documents.append(doc)

        if not all_documents:
            return {"success": True, "has_research": False, "suggested_description": ""}

        # Build context from documents
        doc_summaries = []
        for doc in all_documents[:15]:
            title = doc.get("metadata", {}).get("title", "")
            content = doc.get("content", "")[:1000]
            source = doc.get("metadata", {}).get("source_type", "document")
            if title or content:
                doc_summaries.append(f"[{source}] {title}\n{content}")

        combined_context = "\n\n---\n\n".join(doc_summaries)

        # Use GPT to synthesize a research description
        client = AzureOpenAI(
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version="2024-12-01-preview",
            azure_endpoint="https://rishi-mihfdoty-eastus2.cognitiveservices.azure.com"
        )

        synthesis_prompt = f"""Based on the following research documents from a lab's knowledge base, write a comprehensive research description that could be used to describe their current research focus for journal publication assessment.

The description should:
1. Identify the main research area(s) and field
2. Describe the methodologies and techniques commonly used
3. Highlight key findings or research directions
4. Be written in first person plural (we/our)
5. Be 100-200 words, suitable for pasting into a journal analyzer

Documents:
{combined_context[:8000]}

Write ONLY the research description paragraph, nothing else. Start directly with the research content."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": synthesis_prompt}],
            temperature=0.7,
            max_tokens=500
        )

        suggested_description = response.choices[0].message.content.strip()

        # Extract key research areas
        areas_prompt = f"""From the research description below, extract:
1. research_areas: List 2-4 main research areas/topics (short phrases)
2. methodologies: List 2-4 key methodologies or techniques used
3. recent_focus: One sentence about their most recent research focus

Research description:
{suggested_description}

Return as JSON with keys: research_areas (array), methodologies (array), recent_focus (string)"""

        areas_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": areas_prompt}],
            temperature=0.3,
            max_tokens=300,
            response_format={"type": "json_object"}
        )

        try:
            areas_data = json.loads(areas_response.choices[0].message.content)
        except:
            areas_data = {"research_areas": [], "methodologies": [], "recent_focus": ""}

        summary_data = {
            "success": True,
            "has_research": True,
            "suggested_description": suggested_description,
            "research_areas": areas_data.get("research_areas", []),
            "methodologies": areas_data.get("methodologies", []),
            "recent_focus": areas_data.get("recent_focus", ""),
            "document_count": len(all_documents)
        }

        # Store in database
        if db is None:
            db = SessionLocal()
            should_close = True
        else:
            should_close = False

        try:
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            if tenant:
                tenant.research_summary = summary_data
                tenant.research_summary_updated_at = utc_now()
                db.commit()
                print(f"[Journal] Research summary computed and stored for tenant {tenant_id[:8]}")
        finally:
            if should_close:
                db.close()

        return summary_data

    except Exception as e:
        print(f"[Journal] Research summary computation error: {e}", flush=True)
        traceback.print_exc()
        return {"success": False, "error": str(e)}


@journal_bp.route('/research-summary', methods=['GET'])
@require_auth
def get_research_summary():
    """
    Fetch pre-computed research summary for auto-population.
    Returns cached summary if available, otherwise returns empty.
    """
    tenant_id = g.tenant_id

    try:
        from database.models import Tenant, SessionLocal

        db = SessionLocal()
        try:
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()

            if tenant and tenant.research_summary:
                summary = tenant.research_summary
                summary["cached"] = True
                summary["updated_at"] = tenant.research_summary_updated_at.isoformat() if tenant.research_summary_updated_at else None
                return jsonify(summary), 200

            # No cached summary - return empty (computation happens during sync)
            return jsonify({
                "success": True,
                "has_research": False,
                "suggested_description": "",
                "message": "Research summary not yet computed. It will be generated after your next document sync.",
                "cached": False
            }), 200

        finally:
            db.close()

    except Exception as e:
        print(f"[Journal] Research summary fetch error: {e}", flush=True)
        return jsonify({
            "success": False,
            "error": str(e),
            "suggested_description": ""
        }), 500


@journal_bp.route('/research-summary/refresh', methods=['POST'])
@require_auth
def refresh_research_summary():
    """
    Manually trigger research summary computation.
    """
    tenant_id = g.tenant_id

    try:
        result = compute_research_summary(tenant_id)
        return jsonify(result), 200
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@journal_bp.route('/analyze-with-context', methods=['POST'])


@journal_bp.route('/analyze-with-context', methods=['POST'])
@require_auth
def analyze_manuscript_with_context():
    """
    Analyze a manuscript with lab-specific context from the knowledge base.
    Requires authentication. Uses relevant documents from the user's lab to
    provide personalized recommendations based on past research and publications.

    SSE stream includes additional 'context' event with lab documents used.
    """
    tenant_id = g.tenant_id

    # Check if this is a text-based submission
    research_text = request.form.get('text', '').strip()

    # Optional: user-provided publication year
    user_publication_year = None
    pub_year_str = request.form.get('publication_year', '').strip()
    if pub_year_str:
        try:
            user_publication_year = int(pub_year_str)
        except ValueError:
            pass

    # Read file bytes immediately if present
    file_bytes = None
    filename = ''
    ext = ''

    if 'file' in request.files:
        file = request.files['file']
        filename = file.filename or ''
        if '.' in filename:
            ext = '.' + filename.rsplit('.', 1)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            err_ext = ext or 'unknown'
            return _sse_error_response(f'Unsupported file type: {err_ext}. Please upload a PDF or DOCX file.')
        file_bytes = file.read()
        if len(file_bytes) > MAX_FILE_SIZE:
            return _sse_error_response('File too large. Maximum size is 50MB.')
        if len(file_bytes) == 0:
            return _sse_error_response('File is empty.')

    # Validate input
    if not research_text and not file_bytes:
        return _sse_error_response('No file or research description provided. Please upload a PDF/DOCX or describe your research.')

    if research_text:
        word_count = len(research_text.split())
        if word_count < 50:
            return _sse_error_response(f'Please provide at least 50 words describing your research (currently {word_count}).')

    # Create database session for diverse document fetching
    from database.models import SessionLocal
    db = SessionLocal()

    def generate():
        nonlocal research_text

        try:
            # Parse file if provided
            parsed_text = research_text
            if file_bytes:
                yield f"event: progress\ndata: {json.dumps({'step': 0, 'message': 'Parsing manuscript...', 'percent': 2})}\n\n"
                try:
                    from parsers.document_parser import DocumentParser
                    parser = DocumentParser()
                    parsed_text = parser.parse_file_bytes(file_bytes, filename)
                    if not parsed_text or len(parsed_text) < 100:
                        yield f"event: error\ndata: {json.dumps({'error': 'Could not extract text from file. Please try a different file or paste your text.'})}\n\n"
                        return
                except Exception as e:
                    yield f"event: error\ndata: {json.dumps({'error': f'Error parsing file: {str(e)}'})}\n\n"
                    return

            # Step 1: Fetch lab context based on the research topic
            yield f"event: progress\ndata: {json.dumps({'step': 0, 'message': 'Searching lab knowledge base for relevant context...', 'percent': 5})}\n\n"

            # Extract key terms from the first 2000 chars for context search
            search_query = parsed_text[:2000]
            lab_context = _fetch_lab_context(search_query, tenant_id, db=db, top_k=8)

            # Emit context event so frontend knows what documents were used
            yield f"event: context\ndata: {json.dumps({'documents_used': lab_context.get('count', 0), 'has_context': bool(lab_context.get('summary'))})}\n\n"

            # Step 2: Enhance the research text with STRUCTURED lab context
            profile = lab_context.get('profile')
            doc_count = lab_context.get('count', 0)

            if lab_context.get('summary') and profile:
                # Generate and emit detailed context analysis with sources
                try:
                    yield f"event: progress\ndata: {json.dumps({'step': 0, 'message': 'Analyzing lab profile against manuscript...', 'percent': 8})}\n\n"
                    context_analysis = _generate_journal_context_analysis(profile, parsed_text[:3000])
                    context_analysis['has_context'] = True
                    yield f"event: context_analysis\ndata: {json.dumps(context_analysis)}\n\n"
                except Exception as e:
                    print(f"[Journal] Context analysis failed: {e}")
                    yield f"event: context_analysis\ndata: {json.dumps({'has_context': False, 'error': str(e), 'sources': profile.get('sources', {})})}\n\n"
                # Build context-aware instructions
                context_instructions = """
=== CONTEXT-AWARE ANALYSIS INSTRUCTIONS ===
You have access to this researcher's lab profile. Use it to:

1. **COMPARE** this manuscript to their past work:
   - Is this consistent with their usual research focus?
   - Does it use their typical methodologies?
   - Is it a new direction that might need different journals?

2. **LEVERAGE PUBLICATION HISTORY**:
   - Recommend journals where they've successfully published before (if appropriate)
   - Consider their typical impact tier when setting expectations
   - Note if this manuscript quality matches their track record

3. **CHECK EQUIPMENT/EXPERTISE FIT**:
   - Verify the manuscript's methods match their known capabilities
   - Flag if they're proposing techniques outside their documented expertise

4. **PROVIDE EXPLICIT REASONING**:
   - In your recommendations, explicitly state HOW the lab profile influenced your suggestions
   - Say things like "Given your history publishing in X..." or "Since your lab specializes in Y..."

"""
                enhanced_text = f"""
{context_instructions}

=== LAB PROFILE ===
{lab_context['summary']}

Typical Publication Tier: {profile.get('typical_impact_tier', 'Unknown')}
Preferred Journals: {', '.join(profile.get('preferred_journals', [])[:5]) or 'Not enough data'}
Confidence in Profile: {profile.get('confidence_score', 0):.0%}

=== END LAB PROFILE ===

=== MANUSCRIPT/RESEARCH TO ANALYZE ===
{parsed_text}
"""
                print(f"[Journal] Added structured profile from {doc_count} documents (confidence: {profile.get('confidence_score', 0):.0%})", flush=True)
            else:
                # ALWAYS emit context_analysis - even if just a fallback explanation
                no_context_reason = []
                if doc_count == 0:
                    no_context_reason.append("No documents found in your knowledge base")
                elif not profile:
                    no_context_reason.append("Lab profile could not be generated")
                else:
                    no_context_reason.append("No relevant context found for this manuscript")

                fallback_analysis = {
                    "has_context": False,
                    "no_context_reason": "; ".join(no_context_reason) if no_context_reason else "No lab context available",
                    "documents_searched": doc_count,
                    "tip": "Sync more documents (Slack, Google Drive, etc.) to enable personalized journal recommendations"
                }
                yield f"event: context_analysis\ndata: {json.dumps(fallback_analysis)}\n\n"

                enhanced_text = parsed_text
                print(f"[Journal] No lab context available ({fallback_analysis['no_context_reason']}), proceeding with manuscript only", flush=True)

            # Upload manuscript to S3 if file was provided
            manuscript_url = None
            if file_bytes:
                try:
                    import uuid
                    from services.s3_service import S3Service
                    s3 = S3Service()
                    s3_key = f"journal-manuscripts/{uuid.uuid4()}{ext}"
                    content_type = 'application/pdf' if ext == '.pdf' else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                    uploaded_key, err = s3.upload_bytes(file_bytes, s3_key, content_type=content_type)
                    if uploaded_key:
                        manuscript_url = s3.get_presigned_url(uploaded_key, expiration=86400)
                except Exception as e:
                    print(f"[Journal] S3 upload skipped: {e}")

            # Step 3: Run the analysis with enhanced context
            service = get_journal_scorer_service()
            yield from service.analyze_manuscript(
                file_bytes=None,  # Already parsed
                filename='research_with_context.txt',
                manuscript_url=manuscript_url,
                raw_text=enhanced_text,
                user_publication_year=user_publication_year
            )

        except Exception as e:
            print(f"[Journal] Context stream error: {e}", flush=True)
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
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type, Authorization',
        }
    )
    response.implicit_sequence_conversion = False
    return response
