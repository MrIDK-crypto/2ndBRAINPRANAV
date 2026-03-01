"""
Knowledge Gap API Routes
REST endpoints for knowledge gaps, answers, and voice transcription.
"""

import io
import json
from flask import Blueprint, request, jsonify, g

from database.models import (
    SessionLocal, KnowledgeGap, GapAnswer, Document,
    GapStatus, GapCategory, utc_now
)
from services.auth_service import require_auth
from services.knowledge_service import KnowledgeService
from services.embedding_service import get_embedding_service


# Create blueprint
knowledge_bp = Blueprint('knowledge', __name__, url_prefix='/api/knowledge')


def get_db():
    """Get database session"""
    return SessionLocal()


def embed_gap_answer(answer: GapAnswer, tenant_id: str, db):
    """
    Immediately embed a gap answer to Pinecone for RAG access.

    This makes the answer searchable by the chatbot immediately after submission,
    without waiting for the "Complete Process" batch operation.

    Args:
        answer: The GapAnswer object to embed
        tenant_id: Tenant ID for namespace isolation
        db: Database session

    Returns:
        Dict with embedding result
    """
    try:
        embedding_service = get_embedding_service()
        vector_store = embedding_service.vector_store

        # Format answer as document for embedding
        # Use a special ID prefix to distinguish from regular documents
        doc_id = f"gap_answer_{answer.id}"
        content = f"Q: {answer.question_text}\nA: {answer.answer_text}"

        # Prepare document for embedding
        pinecone_docs = [{
            'id': doc_id,
            'content': content,
            'title': f"Knowledge Gap Answer: {answer.question_text[:100]}",
            'metadata': {
                'source_type': 'gap_answer',
                'knowledge_gap_id': answer.knowledge_gap_id,
                'question_index': answer.question_index,
                'user_id': answer.user_id,
                'is_voice': answer.is_voice_transcription,
                'created_at': answer.created_at.isoformat() if answer.created_at else ''
            }
        }]

        # Embed to Pinecone (answers are typically short, so single chunk)
        result = vector_store.embed_and_upsert_documents(
            documents=pinecone_docs,
            tenant_id=tenant_id,
            chunk_size=2000,  # Large enough for most answers
            chunk_overlap=0,  # No overlap for single-chunk answers
            show_progress=False
        )

        print(f"[auto-embed] Gap answer {answer.id} embedded to Pinecone: {result.get('upserted', 0)} chunks")

        return {
            'success': result.get('success', False),
            'chunks': result.get('upserted', 0),
            'doc_id': doc_id
        }

    except Exception as e:
        print(f"[auto-embed] Error embedding gap answer: {e}")
        return {
            'success': False,
            'error': str(e)
        }


# ============================================================================
# GAP ANALYSIS
# ============================================================================

@knowledge_bp.route('/analyze', methods=['POST'])
@require_auth
def analyze_gaps():
    """
    Trigger knowledge gap analysis on documents.

    Request body (optional):
    {
        "project_id": "...",  // Analyze specific project
        "force": false,  // Force re-analysis
        "include_pending": true,  // Include pending/classified docs (default true)
        "mode": "research" | "v3" | "code" | "intelligent" | "goalfirst" | "multistage" | "simple",  // Analysis mode
        "max_documents": 100  // Max docs to analyze (for cost control)
    }

    Modes:
    - "research" (FOR RESEARCH LABS - RECOMMENDED): Multi-source gap detection
      Designed specifically for research labs. Analyzes protocols, Slack, emails,
      Notion, GitHub, and papers together to find:
      - Cross-source contradictions (protocol says X, Slack says Y)
      - Person-locked knowledge ("Ask Sarah, she knows")
      - Unanswered questions from communications
      - Protocol completeness (missing concentrations, times, temps)
      - Tribal knowledge (tips shared informally, not documented)
      - Reproducibility risks (antibody lot numbers, passage limits)

    - "code" (FOR GITHUB): Code-aware gap detection for repositories
      Detects: TODOs/FIXMEs, undocumented functions, missing error handling,
      API documentation gaps, magic values, security issues, architecture concerns

    - "v3": Enhanced 6-stage GPT-4 analysis
      Stage 1: Deep Document Extraction (GPT-4 semantic understanding)
      Stage 2: Knowledge Graph Assembly (entity resolution)
      Stage 3: Multi-Analyzer Gap Detection (8 specialized analyzers)
      Stage 4: LLM Question Generation (contextual questions)
      Stage 5: Intelligent Prioritization (multi-factor scoring)
      Stage 6: Feedback & Learning Loop

    - "intelligent": 6-layer advanced NLP analysis
      Layer 1: Frame-Based Extraction (DECISION, PROCESS, DEFINITION frames)
      Layer 2: Semantic Role Labeling (missing agents, causes, manners)
      Layer 3: Discourse Analysis (claims without evidence)
      Layer 4: Knowledge Graph (missing entity relations, bus factor)
      Layer 5: Cross-Document Verification (contradictions)
      Layer 6: Grounded Question Generation

    - "goalfirst": 4-stage Goal-First Backward Reasoning
      Stage 1: Goal Extraction - Define project goal
      Stage 2: Decision Extraction - Find strategic, scope, timeline, financial decisions
      Stage 3: Alternative Inference - Infer what alternatives existed
      Stage 4: Question Generation - "Why X over Y?" questions for new employees

    - "multistage": 5-stage LLM reasoning for tacit knowledge
      Stage 1: Corpus Understanding
      Stage 2: Expert Mind Simulation
      Stage 3: New Hire Simulation
      Stage 4: Failure Mode Analysis
      Stage 5: Question Synthesis

    - "simple": Basic single-pass analysis (faster, less intelligent)

    Response:
    {
        "success": true,
        "results": {
            "gaps": [...],
            "total_documents_analyzed": 50,
            "categories_found": {"technical": 5, "process": 3},
            "mode": "intelligent"
        }
    }
    """
    try:
        data = request.get_json() or {}
        project_id = data.get('project_id')
        force = data.get('force', False)
        include_pending = data.get('include_pending', True)
        mode = data.get('mode', 'intelligent')  # Default to intelligent for best quality (NLP-based, zero GPT cost)
        max_documents = min(data.get('max_documents', 100), 500)  # Cap at 500

        # Run synchronously for local testing (no Celery/Redis needed)
        db = get_db()
        try:
            service = KnowledgeService(db)
            tenant_id = getattr(g, 'tenant_id', 'local-tenant')

            print(f"[GapAnalysis] Starting {mode} analysis for tenant {tenant_id}")

            # Run the appropriate analysis mode
            if mode == 'code':
                # Code-aware gap detection for GitHub repositories
                from services.code_gap_detector import analyze_code_gaps_with_llm

                # Get GitHub documents
                documents = db.query(Document).filter(
                    Document.tenant_id == tenant_id,
                    Document.is_deleted == False,
                    Document.source_type == 'github'
                ).limit(max_documents).all()

                if not documents:
                    return jsonify({
                        "success": True,
                        "message": "No GitHub documents found. Sync a repository first.",
                        "gaps_created": 0,
                        "result": {"gaps": [], "total_gaps": 0}
                    })

                # Convert to dict format for detector
                doc_dicts = [{
                    'id': str(doc.id),
                    'title': doc.title,
                    'content': doc.content,
                    'source_type': doc.source_type,
                    'metadata': doc.doc_metadata
                } for doc in documents]

                # Create a mapping from file paths to document IDs
                # GitHub doc titles are like "owner/repo - filepath"
                file_path_to_doc_id = {}
                for doc in documents:
                    # Extract file path from title or metadata
                    file_path = None
                    if doc.doc_metadata and doc.doc_metadata.get('file_path'):
                        file_path = doc.doc_metadata.get('file_path')
                    elif ' - ' in doc.title:
                        # Title format: "owner/repo - filepath"
                        file_path = doc.title.split(' - ', 1)[-1]
                    if file_path:
                        file_path_to_doc_id[file_path] = str(doc.id)

                # Also map by document ID directly
                doc_id_set = set(str(doc.id) for doc in documents)

                print(f"[GapAnalysis] Analyzing {len(doc_dicts)} GitHub documents")
                code_result = analyze_code_gaps_with_llm(doc_dicts, max_gaps_per_category=8, use_llm=True)

                # Save gaps to database
                gaps_created = 0

                # Map code gap categories to GapCategory enum
                category_map = {
                    'documentation': GapCategory.TECHNICAL,
                    'todo_fixme': GapCategory.PROCESS,
                    'error_handling': GapCategory.TECHNICAL,
                    'api_documentation': GapCategory.TECHNICAL,
                    'magic_values': GapCategory.CONTEXT,
                    'dependencies': GapCategory.TECHNICAL,
                    'architecture': GapCategory.DECISION,
                    'testing': GapCategory.PROCESS,
                    'security': GapCategory.TECHNICAL,
                    'performance': GapCategory.TECHNICAL
                }

                # Map priority strings to integers (1-5)
                priority_map = {'high': 5, 'medium': 3, 'low': 1}

                for gap_data in code_result.get('gaps', []):
                    # Map category
                    gap_category = category_map.get(gap_data['category'], GapCategory.TECHNICAL)
                    gap_priority = priority_map.get(gap_data.get('priority', 'medium'), 3)

                    # Get the actual document ID for this gap
                    file_path = gap_data.get('file_path')
                    related_doc_ids = []
                    if file_path:
                        # Try to find the document ID from file path
                        doc_id = file_path_to_doc_id.get(file_path)
                        if doc_id:
                            related_doc_ids = [doc_id]

                    # If no specific file, link to all GitHub docs
                    if not related_doc_ids:
                        related_doc_ids = list(doc_id_set)

                    # Create KnowledgeGap record
                    gap = KnowledgeGap(
                        tenant_id=tenant_id,
                        category=gap_category,
                        title=gap_data['title'],
                        description=gap_data['description'],
                        questions=[{
                            'question': gap_data['question'],
                            'evidence': gap_data.get('evidence'),
                            'file_path': gap_data.get('file_path')
                        }],
                        context={
                            'code_category': gap_data['category'],
                            'evidence': gap_data.get('evidence'),
                            'file_path': gap_data.get('file_path'),
                            'line_hint': gap_data.get('line_hint')
                        },
                        priority=gap_priority,
                        status=GapStatus.OPEN,
                        related_document_ids=related_doc_ids
                    )
                    db.add(gap)
                    gaps_created += 1

                db.commit()
                print(f"[GapAnalysis] Created {gaps_created} code-related gaps")

                return jsonify({
                    "success": True,
                    "message": f"Code gap analysis completed - found {gaps_created} gaps",
                    "gaps_created": gaps_created,
                    "result": {
                        "gaps": code_result.get('gaps', []),
                        "total_gaps": code_result.get('total_gaps', 0),
                        "gaps_by_category": code_result.get('gaps_by_category', {}),
                        "documents_analyzed": code_result.get('documents_analyzed', 0),
                        "mode": "code"
                    }
                })

            elif mode == 'intelligent':
                result = service.analyze_gaps_intelligent(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    max_documents=max_documents
                )
            elif mode == 'goalfirst':
                result = service.analyze_gaps_goalfirst(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    max_documents=max_documents
                )
            elif mode == 'multistage':
                result = service.analyze_gaps_multistage(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    max_documents=max_documents
                )
            elif mode == 'research':
                print(f"[GapAnalysis] *** RESEARCH MODE SELECTED ***")
                result = service.analyze_gaps_research(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    max_documents=max_documents
                )
                print(f"[GapAnalysis] Research mode completed, result: {result}")
            else:  # simple or v3
                result = service.analyze_gaps(
                    tenant_id=tenant_id,
                    project_id=project_id,
                    force_reanalyze=force,
                    include_pending=include_pending
                )

            # Handle both dict results and GapAnalysisResult dataclass
            if isinstance(result, dict):
                gaps_created = result.get('gaps_created', 0)
                result_data = result
            elif hasattr(result, 'gaps'):
                # GapAnalysisResult dataclass
                gaps_created = len(result.gaps)
                result_data = {
                    "gaps_created": gaps_created,
                    "total_documents_analyzed": result.total_documents_analyzed,
                    "categories_found": result.categories_found
                }
            else:
                gaps_created = 0
                result_data = {"gaps_created": 0}

            print(f"[GapAnalysis] Created {gaps_created} gaps")

            return jsonify({
                "success": True,
                "message": f"Gap analysis completed (mode: {mode})",
                "gaps_created": gaps_created,
                "result": result_data
            })
        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# LIST GAPS
# ============================================================================

@knowledge_bp.route('/gaps', methods=['GET'])
@require_auth
def list_gaps():
    """
    List knowledge gaps with filtering.

    Query params:
        project_id: filter by project
        status: open, in_progress, answered, verified, closed
        category: decision, technical, process, context, etc.
        limit: page size (default 50)
        offset: page offset

    Response:
    {
        "success": true,
        "gaps": [...],
        "pagination": {...}
    }
    """
    try:
        project_id = request.args.get('project_id')
        status_str = request.args.get('status')
        category_str = request.args.get('category')
        limit = min(int(request.args.get('limit', 50)), 200)
        offset = int(request.args.get('offset', 0))

        # Parse status
        status = None
        if status_str:
            status_map = {
                'open': GapStatus.OPEN,
                'in_progress': GapStatus.IN_PROGRESS,
                'answered': GapStatus.ANSWERED,
                'verified': GapStatus.VERIFIED,
                'closed': GapStatus.CLOSED
            }
            status = status_map.get(status_str.lower())

        # Parse category
        category = None
        if category_str:
            category_map = {
                'decision': GapCategory.DECISION,
                'technical': GapCategory.TECHNICAL,
                'process': GapCategory.PROCESS,
                'context': GapCategory.CONTEXT,
                'relationship': GapCategory.RELATIONSHIP,
                'timeline': GapCategory.TIMELINE,
                'outcome': GapCategory.OUTCOME,
                'rationale': GapCategory.RATIONALE
            }
            category = category_map.get(category_str.lower())

        db = get_db()
        try:
            service = KnowledgeService(db)
            gaps, total = service.get_gaps(
                tenant_id=getattr(g, 'tenant_id', 'local-tenant'),
                project_id=project_id,
                status=status,
                category=category,
                limit=limit,
                offset=offset
            )

            # Enrich gaps with source document titles
            gaps_data = []
            for gap in gaps:
                gap_dict = gap.to_dict(include_answers=False)

                # Check if source_documents already exists in context (from research mode)
                context = gap_dict.get('context') or {}
                if context.get('source_documents'):
                    # Research mode already stored titles
                    gap_dict['source_documents'] = context['source_documents']
                else:
                    # Legacy: resolve document IDs to titles
                    doc_ids = context.get('analyzed_documents') or context.get('source_docs') or []
                    if doc_ids:
                        source_docs = db.query(Document.id, Document.title).filter(
                            Document.id.in_(doc_ids)
                        ).all()
                        gap_dict['source_documents'] = [
                            {'id': doc.id, 'title': doc.title or 'Untitled'}
                            for doc in source_docs
                        ]
                    else:
                        gap_dict['source_documents'] = []

                gaps_data.append(gap_dict)

            return jsonify({
                "success": True,
                "gaps": gaps_data,
                "pagination": {
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "has_more": offset + limit < total
                }
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# GET SINGLE GAP
# ============================================================================

@knowledge_bp.route('/gaps/<gap_id>', methods=['GET'])
@require_auth
def get_gap(gap_id: str):
    """
    Get a single knowledge gap with answers.

    Response:
    {
        "success": true,
        "gap": { ... },
        "answers": [...]
    }
    """
    try:
        db = get_db()
        try:
            tenant_id = getattr(g, 'tenant_id', 'local-tenant')
            gap = db.query(KnowledgeGap).filter(
                KnowledgeGap.id == gap_id,
                KnowledgeGap.tenant_id == tenant_id
            ).first()

            if not gap:
                return jsonify({
                    "success": False,
                    "error": "Knowledge gap not found"
                }), 404

            service = KnowledgeService(db)
            answers = service.get_answers(gap_id, tenant_id)

            return jsonify({
                "success": True,
                "gap": gap.to_dict(include_answers=True),
                "answers": [a.to_dict() for a in answers]
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# SUMMARIZE CONTEXT FOR A GAP
# ============================================================================

@knowledge_bp.route('/gaps/<gap_id>/context', methods=['GET'])
@require_auth
def get_gap_context(gap_id: str):
    """
    Get LLM-summarized context for a knowledge gap question.
    Returns 2-3 sentences explaining what the question is about.

    Response:
    {
        "success": true,
        "context": "This question relates to..."
    }
    """
    try:
        from services.openai_client import get_openai_client

        db = get_db()
        try:
            tenant_id = getattr(g, 'tenant_id', 'local-tenant')
            gap = db.query(KnowledgeGap).filter(
                KnowledgeGap.id == gap_id,
                KnowledgeGap.tenant_id == tenant_id
            ).first()

            if not gap:
                return jsonify({
                    "success": False,
                    "error": "Knowledge gap not found"
                }), 404

            # Get raw data from gap
            gap_dict = gap.to_dict(include_answers=False)
            questions = gap_dict.get('questions', [])
            description = gap_dict.get('description', '')
            category = gap_dict.get('category', '')
            evidence = gap_dict.get('evidence', '')
            raw_context = gap_dict.get('context', '')
            if isinstance(raw_context, str):
                try:
                    raw_context = json.loads(raw_context)
                except (json.JSONDecodeError, TypeError):
                    raw_context = {}
            raw_context = raw_context or {}

            # Build question text
            question_text = description
            if questions and len(questions) > 0:
                if isinstance(questions[0], dict):
                    question_text = questions[0].get('text', description)
                else:
                    question_text = questions[0]

            # Extract evidence from context fields
            evidence_quote = raw_context.get('evidence_quote', '') if isinstance(raw_context, dict) else ''
            suggested_respondent = raw_context.get('suggested_respondent', '') if isinstance(raw_context, dict) else ''
            business_risk = raw_context.get('business_risk', '') if isinstance(raw_context, dict) else ''

            # Fetch actual source document excerpts for evidence grounding
            source_doc_ids = raw_context.get('analyzed_documents', []) if isinstance(raw_context, dict) else []
            source_doc_ids = source_doc_ids or raw_context.get('source_docs', []) if isinstance(raw_context, dict) else []
            source_excerpts = ""
            if source_doc_ids:
                source_docs = db.query(Document).filter(
                    Document.id.in_(source_doc_ids[:5])
                ).all()
                for sdoc in source_docs:
                    content_snippet = (sdoc.content or '')[:500]
                    if content_snippet:
                        source_excerpts += f"\n- [{sdoc.title or 'Untitled'}]: \"{content_snippet}...\""

            # Build evidence-based prompt
            prompt = f"""Given a knowledge gap and its source evidence, write 2-3 sentences of EVIDENCE-BASED context.
Do NOT invent information. Only use facts from the evidence provided below.

Knowledge Gap: {question_text}
Category: {category or 'General'}
Gap Description: {description[:300]}
{f'Evidence Quote: "{evidence_quote}"' if evidence_quote else ''}
{f'Suggested Respondent: {suggested_respondent}' if suggested_respondent else ''}
{f'Business Risk: {business_risk}' if business_risk else ''}
{f'Source Document Excerpts:{source_excerpts}' if source_excerpts else ''}

RULES:
- Only state facts found in the evidence above
- If the evidence mentions specific people, systems, or dates, include them
- Explain WHY this gap matters based on the evidence, not speculation
- If there isn't enough evidence, say what IS known and what needs clarification"""

            # Call LLM
            client = get_openai_client()
            response = client.chat_completion(
                messages=[
                    {"role": "system", "content": "You are a knowledge management analyst. Provide factual, evidence-based context summaries. Never invent information — only reference what's in the provided evidence."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=200
            )

            context_summary = response.choices[0].message.content.strip()

            return jsonify({
                "success": True,
                "context": context_summary,
                "gap_id": gap_id
            })

        finally:
            db.close()

    except Exception as e:
        print(f"[Context Summary] Error: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# SUBMIT ANSWER
# ============================================================================

@knowledge_bp.route('/gaps/<gap_id>/answers', methods=['POST'])
@require_auth
def submit_answer(gap_id: str):
    """
    Submit an answer to a knowledge gap question.

    Request body:
    {
        "question_index": 0,
        "answer_text": "The answer is..."
    }

    Response:
    {
        "success": true,
        "answer": { ... }
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "Request body required"
            }), 400

        question_index = data.get('question_index')
        answer_text = data.get('answer_text', '').strip()

        if question_index is None:
            return jsonify({
                "success": False,
                "error": "question_index required"
            }), 400

        if not answer_text:
            return jsonify({
                "success": False,
                "error": "answer_text required"
            }), 400

        db = get_db()
        try:
            service = KnowledgeService(db)
            answer, error = service.submit_answer(
                gap_id=gap_id,
                question_index=question_index,
                answer_text=answer_text,
                user_id=getattr(g, 'user_id', 'local-test-user'),
                tenant_id=getattr(g, 'tenant_id', 'local-tenant')
            )

            if error:
                return jsonify({
                    "success": False,
                    "error": error
                }), 400

            # Auto-embed the answer to Pinecone immediately
            # This makes it searchable by the chatbot right away
            tenant_id = getattr(g, 'tenant_id', 'local-tenant')
            embed_result = embed_gap_answer(answer, tenant_id, db)

            return jsonify({
                "success": True,
                "answer": answer.to_dict(),
                "embedded": embed_result.get('success', False),
                "embedding_chunks": embed_result.get('chunks', 0)
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@knowledge_bp.route('/gaps/<gap_id>/answers/<answer_id>', methods=['PUT'])
@require_auth
def update_answer(gap_id: str, answer_id: str):
    """
    Update an existing answer.

    Request body:
    {
        "answer_text": "Updated answer..."
    }
    """
    try:
        data = request.get_json()

        if not data or not data.get('answer_text'):
            return jsonify({
                "success": False,
                "error": "answer_text required"
            }), 400

        db = get_db()
        try:
            service = KnowledgeService(db)
            success, error = service.update_answer(
                answer_id=answer_id,
                answer_text=data['answer_text'],
                user_id=getattr(g, 'user_id', 'local-test-user'),
                tenant_id=getattr(g, 'tenant_id', 'local-tenant')
            )

            if not success:
                return jsonify({
                    "success": False,
                    "error": error
                }), 400

            return jsonify({"success": True})

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# VOICE TRANSCRIPTION
# ============================================================================

@knowledge_bp.route('/transcribe', methods=['POST'])
@require_auth
def transcribe_audio():
    """
    Transcribe audio file using Whisper.

    Request:
        multipart/form-data with 'audio' file

    Response:
    {
        "success": true,
        "transcription": {
            "text": "...",
            "confidence": 0.95,
            "language": "en",
            "duration_seconds": 12.5
        }
    }
    """
    try:
        if 'audio' not in request.files:
            return jsonify({
                "success": False,
                "error": "No audio file provided"
            }), 400

        audio_file = request.files['audio']
        audio_data = audio_file.read()
        filename = audio_file.filename or "audio.wav"

        language = request.form.get('language')

        db = get_db()
        try:
            service = KnowledgeService(db)
            result = service.transcribe_audio(
                audio_data=audio_data,
                filename=filename,
                language=language
            )

            if not result.text:
                return jsonify({
                    "success": False,
                    "error": "Transcription failed",
                    "details": result.segments
                }), 500

            return jsonify({
                "success": True,
                "transcription": {
                    "text": result.text,
                    "confidence": result.confidence,
                    "language": result.language,
                    "duration_seconds": result.duration_seconds,
                    "segments": result.segments
                }
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@knowledge_bp.route('/gaps/<gap_id>/voice-answer', methods=['POST'])
@require_auth
def submit_voice_answer(gap_id: str):
    """
    Submit voice answer - transcribe and save.

    Request:
        multipart/form-data with:
        - 'audio': audio file
        - 'question_index': question index

    Response:
    {
        "success": true,
        "answer": { ... },
        "transcription": { ... }
    }
    """
    try:
        if 'audio' not in request.files:
            return jsonify({
                "success": False,
                "error": "No audio file provided"
            }), 400

        question_index = request.form.get('question_index')
        if question_index is None:
            return jsonify({
                "success": False,
                "error": "question_index required"
            }), 400

        question_index = int(question_index)

        audio_file = request.files['audio']
        audio_data = audio_file.read()
        filename = audio_file.filename or "audio.wav"

        db = get_db()
        try:
            service = KnowledgeService(db)
            answer, error = service.transcribe_and_answer(
                gap_id=gap_id,
                question_index=question_index,
                audio_data=audio_data,
                filename=filename,
                user_id=getattr(g, 'user_id', 'local-test-user'),
                tenant_id=getattr(g, 'tenant_id', 'local-tenant'),
                save_audio=True
            )

            if error:
                return jsonify({
                    "success": False,
                    "error": error
                }), 400

            # Auto-embed the voice answer to Pinecone immediately
            tenant_id = getattr(g, 'tenant_id', 'local-tenant')
            embed_result = embed_gap_answer(answer, tenant_id, db)

            return jsonify({
                "success": True,
                "answer": answer.to_dict(),
                "embedded": embed_result.get('success', False),
                "embedding_chunks": embed_result.get('chunks', 0)
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# INDEX MANAGEMENT
# ============================================================================

# ============================================================================
# COMPLETE PROCESS - Finalize knowledge gaps into RAG
# ============================================================================

@knowledge_bp.route('/complete-process', methods=['POST'])
@require_auth
def complete_process():
    """
    Complete the knowledge transfer process.

    Integrates all answered knowledge gap questions into the RAG embedding index,
    making them available for chat queries. Can be called even if not all questions
    are answered - it will integrate whatever answers exist.

    Request body (optional):
    {
        "mark_completed": true  // Whether to mark gaps with answers as completed
    }

    Response:
    {
        "success": true,
        "results": {
            "answers_integrated": 15,
            "documents_indexed": 50,
            "chunks_created": 250,
            "gaps_completed": 5,
            "message": "Successfully integrated 15 answers into RAG knowledge base"
        }
    }
    """
    try:
        data = request.get_json() or {}
        mark_completed = data.get('mark_completed', True)

        db = get_db()
        try:
            service = KnowledgeService(db)
            result = service.complete_knowledge_process(
                tenant_id=getattr(g, 'tenant_id', 'local-tenant'),
                mark_completed=mark_completed
            )

            if not result.get("success"):
                return jsonify({
                    "success": False,
                    "error": result.get("error", "Unknown error")
                }), 500

            return jsonify({
                "success": True,
                "results": {
                    "answers_integrated": result.get("answers_integrated", 0),
                    "documents_indexed": result.get("documents_indexed", 0),
                    "chunks_created": result.get("chunks_created", 0),
                    "gaps_completed": result.get("gaps_completed", 0),
                    "message": result.get("message", "Process completed")
                }
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# INDEX MANAGEMENT
# ============================================================================

@knowledge_bp.route('/rebuild-index', methods=['POST'])
@require_auth
def rebuild_index():
    """
    Rebuild the embedding index for the tenant.

    Request body (optional):
    {
        "force": false
    }

    Response:
    {
        "success": true,
        "results": {
            "documents_processed": 100,
            "answers_included": 25,
            "chunks_created": 500
        }
    }
    """
    try:
        data = request.get_json() or {}
        force = data.get('force', False)

        db = get_db()
        try:
            service = KnowledgeService(db)
            results = service.rebuild_embedding_index(
                tenant_id=getattr(g, 'tenant_id', 'local-tenant'),
                force=force
            )

            if results.get("error"):
                return jsonify({
                    "success": False,
                    "error": results["error"]
                }), 500

            return jsonify({
                "success": True,
                "results": results
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# STATISTICS
# ============================================================================

@knowledge_bp.route('/stats', methods=['GET'])
@require_auth
def get_stats():
    """
    Get knowledge gap statistics.

    Response:
    {
        "success": true,
        "stats": {
            "by_status": {...},
            "by_category": {...},
            "total_gaps": 50,
            "total_answers": 120,
            "voice_answers": 30
        }
    }
    """
    try:
        db = get_db()
        try:
            service = KnowledgeService(db)
            tenant_id = getattr(g, 'tenant_id', 'local-tenant')
            stats = service.get_gap_stats(tenant_id)

            return jsonify({
                "success": True,
                "stats": stats
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# UPDATE GAP STATUS
# ============================================================================

@knowledge_bp.route('/gaps/<gap_id>/status', methods=['PUT'])
@require_auth
def update_gap_status(gap_id: str):
    """
    Update knowledge gap status.

    Request body:
    {
        "status": "answered" | "verified" | "closed"
    }
    """
    try:
        data = request.get_json()

        if not data or not data.get('status'):
            return jsonify({
                "success": False,
                "error": "status required"
            }), 400

        status_map = {
            'open': GapStatus.OPEN,
            'in_progress': GapStatus.IN_PROGRESS,
            'answered': GapStatus.ANSWERED,
            'verified': GapStatus.VERIFIED,
            'closed': GapStatus.CLOSED
        }

        new_status = status_map.get(data['status'].lower())
        if not new_status:
            return jsonify({
                "success": False,
                "error": "Invalid status"
            }), 400

        db = get_db()
        try:
            tenant_id = getattr(g, 'tenant_id', 'local-tenant')
            gap = db.query(KnowledgeGap).filter(
                KnowledgeGap.id == gap_id,
                KnowledgeGap.tenant_id == tenant_id
            ).first()

            if not gap:
                return jsonify({
                    "success": False,
                    "error": "Gap not found"
                }), 404

            gap.status = new_status
            gap.updated_at = utc_now()

            if new_status == GapStatus.CLOSED:
                gap.closed_at = utc_now()

            db.commit()

            return jsonify({
                "success": True,
                "gap": gap.to_dict()
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================================
# GAP FEEDBACK (for improving detection accuracy)
# ============================================================================

@knowledge_bp.route('/gaps/<gap_id>/feedback', methods=['POST'])
@require_auth
def submit_gap_feedback(gap_id: str):
    """
    Submit feedback on a knowledge gap's usefulness.
    This helps improve gap detection accuracy over time.

    Request body:
    {
        "useful": true | false,
        "comment": "Optional comment explaining why"
    }

    Response:
    {
        "success": true,
        "gap": { ... with updated feedback counts }
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "Request body required"
            }), 400

        useful = data.get('useful')
        comment = data.get('comment', '').strip()

        if useful is None:
            return jsonify({
                "success": False,
                "error": "'useful' field required (true/false)"
            }), 400

        db = get_db()
        try:
            tenant_id = getattr(g, 'tenant_id', 'local-tenant')
            user_id = getattr(g, 'user_id', 'local-test-user')
            gap = db.query(KnowledgeGap).filter(
                KnowledgeGap.id == gap_id,
                KnowledgeGap.tenant_id == tenant_id
            ).first()

            if not gap:
                return jsonify({
                    "success": False,
                    "error": "Gap not found"
                }), 404

            # Update feedback counts
            if useful:
                gap.feedback_useful = (gap.feedback_useful or 0) + 1
            else:
                gap.feedback_not_useful = (gap.feedback_not_useful or 0) + 1

            # Add comment if provided
            if comment:
                comments = gap.feedback_comments or []
                comments.append({
                    "user_id": user_id,
                    "useful": useful,
                    "comment": comment,
                    "timestamp": utc_now().isoformat()
                })
                gap.feedback_comments = comments

            gap.updated_at = utc_now()
            db.commit()

            return jsonify({
                "success": True,
                "gap": gap.to_dict(),
                "message": "Feedback recorded. Thank you for helping improve gap detection!"
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@knowledge_bp.route('/gaps/stats', methods=['GET'])
@require_auth
def get_gap_stats():
    """
    Get statistics about knowledge gaps including feedback summary.

    Response:
    {
        "success": true,
        "stats": {
            "total_gaps": 50,
            "open_gaps": 30,
            "closed_gaps": 20,
            "total_useful_feedback": 100,
            "total_not_useful_feedback": 20,
            "feedback_ratio": 0.83,
            "by_category": {...},
            "by_source_pattern": {...}
        }
    }
    """
    try:
        from sqlalchemy import func

        db = get_db()
        try:
            tenant_id = getattr(g, 'tenant_id', 'local-tenant')

            # Basic counts
            total = db.query(func.count(KnowledgeGap.id)).filter(
                KnowledgeGap.tenant_id == tenant_id
            ).scalar()

            open_count = db.query(func.count(KnowledgeGap.id)).filter(
                KnowledgeGap.tenant_id == tenant_id,
                KnowledgeGap.status == GapStatus.OPEN
            ).scalar()

            closed_count = db.query(func.count(KnowledgeGap.id)).filter(
                KnowledgeGap.tenant_id == tenant_id,
                KnowledgeGap.status == GapStatus.CLOSED
            ).scalar()

            # Feedback totals
            useful_total = db.query(func.sum(KnowledgeGap.feedback_useful)).filter(
                KnowledgeGap.tenant_id == tenant_id
            ).scalar() or 0

            not_useful_total = db.query(func.sum(KnowledgeGap.feedback_not_useful)).filter(
                KnowledgeGap.tenant_id == tenant_id
            ).scalar() or 0

            total_feedback = useful_total + not_useful_total
            feedback_ratio = useful_total / total_feedback if total_feedback > 0 else 0

            # By category
            category_counts = {}
            for category in GapCategory:
                count = db.query(func.count(KnowledgeGap.id)).filter(
                    KnowledgeGap.tenant_id == tenant_id,
                    KnowledgeGap.category == category
                ).scalar()
                category_counts[category.value] = count

            return jsonify({
                "success": True,
                "stats": {
                    "total_gaps": total,
                    "open_gaps": open_count,
                    "closed_gaps": closed_count,
                    "total_useful_feedback": useful_total,
                    "total_not_useful_feedback": not_useful_total,
                    "feedback_ratio": round(feedback_ratio, 2),
                    "by_category": category_counts
                }
            })

        finally:
            db.close()

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =============================================================================
# PROTOCOL TRAINING ENDPOINTS
# =============================================================================

@knowledge_bp.route('/protocol-training/ingest', methods=['POST'])
@require_auth
def trigger_protocol_ingestion():
    """Trigger protocol corpus ingestion (admin only)."""
    try:
        data = request.get_json(silent=True) or {}
        sources = data.get('sources', None)
        max_protocols = data.get('max_protocols', 5000)

        from tasks.protocol_training_tasks import ingest_protocol_corpus
        task = ingest_protocol_corpus.delay(sources=sources, max_protocols=max_protocols)

        return jsonify({
            "success": True,
            "task_id": task.id,
            "message": f"Protocol corpus ingestion started (sources: {sources or 'all'})"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@knowledge_bp.route('/protocol-training/train', methods=['POST'])
@require_auth
def trigger_protocol_training():
    """Trigger ML model training (admin only)."""
    try:
        from tasks.protocol_training_tasks import train_protocol_models
        task = train_protocol_models.delay()

        return jsonify({
            "success": True,
            "task_id": task.id,
            "message": "Protocol model training started"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@knowledge_bp.route('/protocol-training/stats', methods=['GET'])
@require_auth
def get_protocol_training_stats():
    """Get protocol corpus and training statistics."""
    import os
    try:
        corpus_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'protocol_corpus')
        models_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'protocol_models')

        stats = {
            "corpus_available": False,
            "models_available": False,
            "corpus_stats": {},
            "models": {},
        }

        stats_file = os.path.join(corpus_dir, 'corpus_stats.json')
        if os.path.exists(stats_file):
            with open(stats_file, 'r') as f:
                stats['corpus_stats'] = json.load(f)
            stats['corpus_available'] = True

        for model_name in ['content_classifier.joblib', 'missing_step_detector.joblib', 'completeness_scorer.joblib']:
            model_path = os.path.join(models_dir, model_name)
            stats['models'][model_name] = os.path.exists(model_path)

        stats['models_available'] = any(stats['models'].values())

        return jsonify({"success": True, "data": stats})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
